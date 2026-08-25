-- sql/tuning_queries.sql -- the measurement harness for issue #17.
--
-- NOT part of the build. scripts/load_db.py never runs this; it is run by hand, twice, to produce the before-and-after numbers that the physical design section of the report is made of.
--
-- HOW TO TAKE THE MEASUREMENT
--
--   1 / Load the bulk data with no indexes:
--         .venv/bin/python scripts/load_db.py --yes --bulk --skip-indexes
--
--   2 / Capture the "before" run:
--         cs166_psql -d jcarb044_DB -f sql/tuning_queries.sql > docs/tuning_before.txt
--
--   3 / Build the indexes:
--         cs166_psql -d jcarb044_DB -f sql/indexes.sql
--
--   4 / Capture the "after" run:
--         cs166_psql -d jcarb044_DB -f sql/tuning_queries.sql > docs/tuning_after.txt
--
--   5 / Put the demo dataset back before doing anything else:
--         .venv/bin/python scripts/load_db.py --yes
--
-- Step 5 matters. Leaving the bulk data loaded means browse shows four and a half thousand auctions during the demo.
--
-- READING THE OUTPUT. EXPLAIN ANALYZE actually runs the query and reports what happened, so every number is measured rather than estimated. Four things are worth pulling out of each plan:
--
--   Seq Scan vs Index Scan     which access method the planner chose. This is the headline.
--   rows=N ... actual rows=N   the estimate against reality. A large gap means the statistics are stale -- run ANALYZE.
--   Sort                       a sort node that disappears after indexing is a real win, because the index delivered the order for free.
--   Execution Time             the number for the report. Run each query more than once and take a later run; the first touches cold cache and is not representative.
--
-- Each query below is preceded by a comment naming the application function it comes from, so the report can say which feature got faster rather than just quoting SQL.


\timing on


-- 1. bids.history() -- the bid history under the auction detail screen ------------------------------
--
-- The single best demonstration in the set. Before indexing this is a full scan of every bid in the database followed by a sort; afterwards it should be an index scan with no sort node at all, because idx_bid_auction_amount stores the rows in exactly the order asked for.

EXPLAIN (ANALYZE, BUFFERS)
SELECT bid_id, buyer_login, bid_amount, bid_timestamp
FROM bid
WHERE auction_id = 500
ORDER BY bid_amount DESC;


-- 2. bids.list_for_buyer() -- "your bids" ------------------------------------------------------------
--
-- Three-table join filtered by one buyer. Watch bid go from a sequential scan to an index scan on idx_bid_buyer.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    b.bid_id,
    b.auction_id,
    i.item_name,
    b.bid_amount,
    a.current_highest_bid,
    a.auction_status,
    b.bid_timestamp,
    CASE
        WHEN a.auction_status = 'Closed' AND a.winner_login = b.buyer_login THEN 'Won'
        WHEN a.auction_status = 'Closed' THEN 'Lost'
        WHEN b.bid_amount = a.current_highest_bid THEN 'Leading'
        ELSE 'Outbid'
    END AS outcome
FROM bid b
JOIN auction a ON a.auction_id = b.auction_id
JOIN item i ON i.item_id = a.item_id
WHERE b.buyer_login = 'bulkbuyer0042'
ORDER BY b.bid_timestamp DESC;


-- 3. auctions.browse() -- every open auction ---------------------------------------------------------
--
-- The partial index idx_auction_active is the one being tested here. Two-value columns are exactly where the planner may decide a sequential scan is cheaper, so this query is as likely to show no improvement as a large one. Report whichever happens.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    a.auction_id,
    i.item_name,
    i.category,
    i.starting_price,
    a.current_highest_bid,
    a.seller_login
FROM auction a
JOIN item i ON i.item_id = a.item_id
WHERE a.auction_status = 'Active'
ORDER BY a.auction_id DESC;


-- 4. auctions.search() -- category plus a price range ------------------------------------------------
--
-- Two indexes are candidates at once, idx_item_category and idx_item_starting_price, and PostgreSQL will pick one rather than both unless it decides a bitmap combination is worthwhile. A BitmapAnd node in the plan means it used both, which is worth pointing at if it appears.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    a.auction_id,
    i.item_name,
    i.category,
    i.starting_price,
    a.current_highest_bid,
    a.auction_status,
    a.seller_login
FROM auction a
JOIN item i ON i.item_id = a.item_id
WHERE a.auction_status = 'Active'
  AND i.category ILIKE 'Books'
  AND i.starting_price >= 100
  AND i.starting_price <= 300
ORDER BY a.auction_id DESC;


-- 5. auctions.search() by name -- THE ONE THAT DOES NOT IMPROVE ---------------------------------------
--
-- Included deliberately. ILIKE '%term%' has a leading wildcard, so no B-tree can serve it and this stays a sequential scan before and after. Showing a query that indexing cannot help is what makes the rest of the numbers credible, and the explanation -- a B-tree is sorted by the start of the string, and this pattern does not know its own start -- is a good thing to have ready.

EXPLAIN (ANALYZE, BUFFERS)
SELECT a.auction_id, i.item_name, i.category, i.starting_price
FROM auction a
JOIN item i ON i.item_id = a.item_id
WHERE a.auction_status = 'Active'
  AND i.item_name ILIKE '%Item 3%';


-- 6. reports.top_bidders() -----------------------------------------------------------------------------
--
-- The heaviest query in the application: a LEFT JOIN over the whole bid table, grouped, with a correlated subquery that runs once per Buyer. With 400 buyers and no index on auction.winner_login, that subquery alone is 400 sequential scans.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    u.login,
    u.favorite_category,
    COUNT(b.bid_id) AS bids_placed,
    COUNT(DISTINCT b.auction_id) AS auctions_bid_on,
    MAX(b.bid_amount) AS highest_bid,
    (SELECT COUNT(*) FROM auction a WHERE a.winner_login = u.login) AS auctions_won
FROM users u
LEFT JOIN bid b ON b.buyer_login = u.login
WHERE u.role = 'Buyer'
GROUP BY u.login, u.favorite_category
ORDER BY bids_placed DESC, highest_bid DESC NULLS LAST;


-- 7. reports.revenue_by_category() ----------------------------------------------------------------------

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    i.category,
    COUNT(*) AS items_sold,
    SUM(a.current_highest_bid) AS revenue,
    ROUND(AVG(a.current_highest_bid), 2) AS average_sale,
    MAX(a.current_highest_bid) AS largest_sale
FROM auction a
JOIN item i ON i.item_id = a.item_id
WHERE a.auction_status = 'Closed'
  AND a.winner_login IS NOT NULL
GROUP BY i.category
HAVING SUM(a.current_highest_bid) > 0
ORDER BY revenue DESC;


-- 8. reports.unpaid_wins() -- the anti-join ---------------------------------------------------------------
--
-- Expected to be fast in both runs, because payment.auction_id is UNIQUE and therefore already indexed by the schema itself. That is the point of including it: a query that was already fast is not evidence an index helped, and knowing which measurements are uninformative is part of reading them honestly.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    a.auction_id,
    i.item_name,
    i.category,
    a.winner_login,
    a.current_highest_bid AS amount_owed,
    a.seller_login
FROM auction a
JOIN item i ON i.item_id = a.item_id
LEFT JOIN payment p ON p.auction_id = a.auction_id
WHERE a.auction_status = 'Closed'
  AND a.winner_login IS NOT NULL
  AND p.payment_id IS NULL
ORDER BY a.current_highest_bid DESC;


-- 9. reports.active_auctions() ------------------------------------------------------------------------------
--
-- A LEFT JOIN from every Active auction into the whole bid table, then grouped. This is where idx_bid_auction_amount should show its largest absolute saving, because the join has thousands of auctions to satisfy rather than one.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    a.auction_id,
    i.item_name,
    i.category,
    a.seller_login,
    i.starting_price,
    a.current_highest_bid,
    COUNT(b.bid_id) AS bids_placed,
    COUNT(DISTINCT b.buyer_login) AS bidders
FROM auction a
JOIN item i ON i.item_id = a.item_id
LEFT JOIN bid b ON b.auction_id = a.auction_id
WHERE a.auction_status = 'Active'
GROUP BY
    a.auction_id,
    i.item_name,
    i.category,
    a.seller_login,
    i.starting_price,
    a.current_highest_bid
ORDER BY a.current_highest_bid DESC, bids_placed DESC;


-- 10. HOW BIG IS ALL OF THIS ANYWAY -------------------------------------------------------------------------
--
-- Indexes are not free: they cost disk and they slow every INSERT, because each write has to update every index on the table. The report should say what was paid, not only what was gained -- and on this server that matters more than usual, since $PGDATA sits on a filesystem that is essentially full.
--
-- Returns nothing before the indexes exist, which is itself the "before" measurement.

SELECT
    indexname,
    tablename,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY pg_relation_size(indexname::regclass) DESC;


-- And the tables they sit on, for comparison.

SELECT
    relname AS table_name,
    to_char(n_live_tup, 'FM999,999,999') AS live_rows,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS all_indexes
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC;


\timing off
