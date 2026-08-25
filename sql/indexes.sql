-- sql/indexes.sql -- the physical database design. Issue #17.
--
-- Run last, after the data is loaded. scripts/load_db.py already does that; --skip-indexes omits this file so the "before" half of a measurement can be taken.
--
-- THE ONE FACT THIS ENTIRE FILE RESTS ON:
--
--     PostgreSQL automatically creates an index for PRIMARY KEY and for UNIQUE. It does NOT create one for a FOREIGN KEY.
--
-- That is not an oversight in our schema, it is how PostgreSQL works, and it surprises people who expect the referencing side to be indexed the way the referenced side is. The consequence here is specific and severe: bid.auction_id is the most heavily joined column in the whole application -- every bid history, every report, every MAX(bid_amount) grouping goes through it -- and in the instructor's schema it has no index whatsoever. With 29,000 bids loaded, all of those are sequential scans over the entire table.
--
-- What our schema gets for free, and therefore what is NOT repeated below:
--     users(login), item(item_id), auction(auction_id), bid(bid_id), payment(payment_id), shipment(shipment_id)   -- PRIMARY KEY
--     users(login, role), auction(item_id), payment(auction_id), shipment(auction_id)                             -- UNIQUE
--
-- Note that payment(auction_id) being UNIQUE is why the won-but-unpaid anti-join is already fast before any of this runs. Worth knowing when reading the measurements: not every query improves, and a query that was already fast is not evidence of anything.
--
-- NO "CREATE INDEX CONCURRENTLY" ANYWHERE IN THIS FILE. It cannot run inside a transaction block, and scripts/load_db.py deliberately wraps every .sql file in one so a failure rolls the whole load back. CONCURRENTLY exists to avoid locking a table that live users are writing to, which is not a situation this project has.
--
-- NO COVERING INDEXES either -- CREATE INDEX ... INCLUDE arrived in PostgreSQL 11 and this server runs 10.23.


-- Dropping first makes the file safe to re-run by hand while measuring.
DROP INDEX IF EXISTS idx_bid_auction_amount;
DROP INDEX IF EXISTS idx_bid_buyer;
DROP INDEX IF EXISTS idx_auction_active;
DROP INDEX IF EXISTS idx_auction_winner;
DROP INDEX IF EXISTS idx_auction_seller;
DROP INDEX IF EXISTS idx_item_category;
DROP INDEX IF EXISTS idx_item_starting_price;
DROP INDEX IF EXISTS idx_item_seller;


-- 1. THE IMPORTANT ONE ----------------------------------------------------------------------------
--
-- SERVES: bids.history(), the bid count and bidder count in reports.active_auctions(), and the MAX(bid_amount) GROUP BY that bulk_seed.sql uses to reconcile current_highest_bid.
--
-- Two columns, and the order is the whole point. A composite B-tree is sorted by its first column, then by its second within each value of the first -- like a phone book sorted by surname then forename. So this index can seek straight to one auction_id and then read its bids already in descending amount order.
--
-- That second part is what turns an index from useful into free. bids.history() is:
--     WHERE auction_id = %s ORDER BY bid_amount DESC
-- Without the index that is a scan of 29,000 rows followed by a sort. With it, PostgreSQL walks directly to the auction's slice and reads it backwards -- no sort step at all, which EXPLAIN will show by the total absence of a Sort node rather than by a faster one.
--
-- DESC is written explicitly even though a B-tree can be read in either direction, because it documents the intent and costs nothing.
--
-- The column order could not be reversed. An index on (bid_amount, auction_id) would be sorted by amount first, so finding one auction's bids would mean looking in 29,000 places.

CREATE INDEX idx_bid_auction_amount ON bid (auction_id, bid_amount DESC);


-- 2. THE OTHER FOREIGN KEY ON bid -------------------------------------------------------------------
--
-- SERVES: bids.list_for_buyer() -- "your bids" -- and the LEFT JOIN in reports.top_bidders().
--
-- Same story as above: a foreign key with no index behind it. Before this, answering "what has buyer1 bid on" means reading every bid in the table and discarding 99.7% of them.
--
-- Single column, because neither query orders by anything else on this table.

CREATE INDEX idx_bid_buyer ON bid (buyer_login);


-- 3. A PARTIAL INDEX, AND THE MOST INTERESTING ONE TO EXPLAIN ----------------------------------------
--
-- SERVES: auctions.browse(), auctions.search() with its default status filter, and reports.active_auctions().
--
-- auction_status holds exactly two values, 'Active' and 'Closed'. Indexing it the obvious way -- CREATE INDEX ON auction (auction_status) -- is usually a waste, and it is worth understanding why rather than just being told. An index earns its cost by eliminating rows. A column with two values eliminates at best half the table, and once a query is going to touch a large fraction of a table anyway, reading the table straight through in physical order beats bouncing between an index and the heap. The planner knows this and will frequently ignore such an index, which is a perfectly correct decision and not a failure.
--
-- WHERE auction_status = 'Active' is what makes this one different. A partial index only contains the rows matching its own WHERE clause, so this index holds only the Active auctions and nothing else. It is smaller, it stays hot in cache, and every query with that same predicate can use it. The Closed rows -- roughly a third of the table, and growing forever as the site ages -- are not in it at all and cost nothing to maintain.
--
-- It also indexes exactly the queries the application actually runs. Nothing in this project asks for "all Closed auctions"; browse and search both ask for Active ones.
--
-- FOR THE REPORT: if the measurement shows the planner choosing a sequential scan anyway, say so and keep the index in the write-up. "We measured it, the planner declined it, and here is the reasoning" is a stronger answer than only presenting the wins.

CREATE INDEX idx_auction_active ON auction (auction_id) WHERE auction_status = 'Active';


-- 4. FINDING WINNERS --------------------------------------------------------------------------------
--
-- SERVES: the correlated subquery in reports.top_bidders() that counts auctions won, and reports.unpaid_wins().
--
-- The correlated subquery is the reason this matters more than it looks. It runs once per Buyer -- 400 times against the bulk dataset -- and each run scans the auction table looking for a winner_login. Four hundred sequential scans of 4,500 rows is close to two million row reads for a single report.
--
-- winner_login is NULL for every Active auction, and PostgreSQL's B-trees do store NULLs. A partial index WHERE winner_login IS NOT NULL would be smaller again; it is left as a plain index here because both queries also benefit from the equality lookup and the difference at this size is not worth a second thing to explain.

CREATE INDEX idx_auction_winner ON auction (winner_login);


-- 5. AND 6. THE REMAINING FOREIGN KEYS --------------------------------------------------------------
--
-- SERVES: "show me my listings" and "show me my auctions" -- issues #8 and #9 -- plus any join from a user to the things they are selling.
--
-- Included for completeness of the physical design rather than because a measurement demanded them. Both are unindexed foreign keys on tables with thousands of rows, which is the same problem as #1 and #2 in a less severe form.

CREATE INDEX idx_auction_seller ON auction (seller_login);
CREATE INDEX idx_item_seller ON item (seller_login);


-- 7. SEARCH BY CATEGORY -----------------------------------------------------------------------------
--
-- SERVES: auctions.search() when a category is supplied, and the GROUP BY in reports.revenue_by_category().
--
-- Ten distinct categories across 5,000 items, so any one of them selects about a tenth of the table. That is roughly the boundary where a B-tree starts paying for itself, which makes this a genuinely interesting row in the results table rather than a foregone conclusion.
--
-- IMPORTANT CAVEAT, and a good thing to be asked about: search uses ILIKE, and this index cannot serve it. A B-tree stores values in sort order, so it can seek on a known prefix -- but ILIKE is case-insensitive, which means 'books' and 'Books' sort to different places, and the index has no way to find both. Making this index usable by that query would mean indexing the expression instead:
--     CREATE INDEX ON item (lower(category));
-- and changing the query to WHERE lower(category) = lower(%s). We did not, because the plain index still serves the report's GROUP BY, and because the honest limitation is more useful to document than to paper over.

CREATE INDEX idx_item_category ON item (category);


-- 8. SEARCH BY PRICE RANGE --------------------------------------------------------------------------
--
-- SERVES: auctions.search() when a price filter is supplied.
--
-- Range queries are what B-trees are best at, and better at than the equality lookups above. Because the index is stored in sorted order, "everything between $100 and $300" is one seek to the lower bound followed by a sequential walk to the upper bound -- no comparisons against rows outside the range at all.
--
-- Prices are spread from $5 to $500 in bulk_seed.sql precisely so this is measurable. A dataset where every item cost about the same would make every range scan return the whole table and prove nothing.

CREATE INDEX idx_item_starting_price ON item (starting_price);


-- WHAT WE DELIBERATELY DID NOT INDEX ------------------------------------------------------------------
--
-- Worth stating in the report, because choosing not to build an index is part of physical design too.
--
--   item_name for the ILIKE '%term%' search. A leading wildcard cannot use a B-tree at all: the index is sorted by the start of the string, and a pattern that does not know its own beginning gives it nothing to seek on. That search is a sequential scan no matter what is built here. The real fix is a trigram index -- CREATE EXTENSION pg_trgm, then a GIN index on item_name gin_trgm_ops -- which needs an extension we did not install on a shared course server. Documented as a limitation rather than pretended away.
--
--   bid_timestamp. Nothing orders by it. bids.history() orders by bid_amount, and because every bid must strictly exceed the previous high, amount order and time order are the same sequence -- so the amount index already delivers chronological order for free.
--
--   payment and shipment. Both are small, and both already have a UNIQUE index on auction_id, which is the only column anything joins them by.


-- REFRESH THE STATISTICS ------------------------------------------------------------------------------
--
-- Creating an index does not by itself tell the planner how useful it will be. ANALYZE recollects the statistics -- row counts, distinct values, distribution -- that the planner uses to decide whether to bother with any of the above. Skipping this can leave a brand new index sitting unused because the planner is still working from numbers taken before the data existed.

ANALYZE item;
ANALYZE auction;
ANALYZE bid;
