-- sql/bulk_seed.sql -- the large dataset, for issue #17's index measurements only.
--
-- WHY THIS FILE EXISTS. sql/seed.sql holds about thirty rows. That is the right size for building features against and for demonstrating them, because every row can be read and checked by eye. It is the wrong size for measuring an index: on thirty rows PostgreSQL sequential-scans everything, because reading the whole table is genuinely cheaper than consulting an index and then fetching the rows anyway. Any EXPLAIN ANALYZE taken against seed.sql is noise, and any speedup it appears to show is measurement error.
--
-- So this file adds volume. Roughly 440 extra users, 5,000 items, 4,500 auctions and 25,000-plus bids.
--
-- RUN IT AFTER seed.sql, NOT INSTEAD OF IT:
--     .venv/bin/python scripts/load_db.py --yes        # schema, extensions, seed, indexes
--     cs166_psql -d jcarb044_DB -f sql/bulk_seed.sql   # then this
--
-- sql/seed.sql IS NEVER EDITED. Everything it creates stays exactly as it was -- the logins admin1, seller1, seller2, buyer1, buyer2, buyer3 and newbie1 all still work with the password pass123, and all seven seeded auction states are untouched. The demo runs against the same rows whether or not this file has been loaded. Every statement below is guarded so it can only ever touch rows it created itself.
--
-- NO setval BLOCK AT THE END, unlike seed.sql. Every INSERT here omits its id column and lets the sequences from extensions.sql do the numbering, which is the same thing the application does. seed.sql needs its setval only because it hard-codes ids so its rows can reference each other.


-- REPEATABLE RANDOMNESS ---------------------------------------------------------------------------
--
-- setseed() fixes the sequence random() will produce for the rest of this session, so loading this file twice on two machines gives byte-identical data. That matters for a measurement: a tuning number nobody else can reproduce is not evidence. Any value works; 0.166 is this course.

SELECT setseed(0.166);


-- CLEAN SLATE -------------------------------------------------------------------------------------
--
-- Makes the file safe to re-run. Everything created below is prefixed 'bulk', so these deletes cannot touch a seeded row even by accident.
-- The order is forced by the foreign keys: shipment and payment point at auction, bid points at auction and users, auction points at item and users, item points at users. Delete children before parents or Postgres refuses.

DELETE FROM shipment WHERE auction_id IN (SELECT auction_id FROM auction WHERE seller_login LIKE 'bulkseller%');
DELETE FROM payment  WHERE auction_id IN (SELECT auction_id FROM auction WHERE seller_login LIKE 'bulkseller%');
DELETE FROM bid      WHERE buyer_login LIKE 'bulkbuyer%';
DELETE FROM auction  WHERE seller_login LIKE 'bulkseller%';
DELETE FROM item     WHERE seller_login LIKE 'bulkseller%';
DELETE FROM users    WHERE login LIKE 'bulk%';


-- USERS -------------------------------------------------------------------------------------------
--
-- 40 sellers and 400 buyers. Volume here is what gives the reports something to aggregate: "top bidders" over four buyers is a list, over four hundred it is a report.
--
-- users is the one table with no sequence, because its primary key is the login string rather than a number. lpad() pads the counter to a fixed width so the logins sort correctly as text -- bulkbuyer0002 before bulkbuyer0010, which plain concatenation would get backwards.
--
-- Passwords stay 'pass123' throughout, matching seed.sql. These accounts are loginable, which is occasionally useful when checking that a report row corresponds to a real user.

INSERT INTO users (login, password, phone_num, address, role, favorite_category)
SELECT
    'bulkseller' || lpad(g::text, 4, '0'),
    'pass123',
    '555-1' || lpad(g::text, 3, '0'),
    g || ' Warehouse Row, Riverside CA',
    'Seller',
    -- Ten categories rather than the seed's six, so GROUP BY reports have enough groups to be interesting and the planner has real selectivity to work with. A column whose every row says 'Electronics' teaches an index nothing.
    (ARRAY['Clothing','Electronics','Books','Music','Home','Sports','Toys','Garden','Tools','Art'])[1 + (g % 10)]
FROM generate_series(1, 40) AS g;

INSERT INTO users (login, password, phone_num, address, role, favorite_category)
SELECT
    'bulkbuyer' || lpad(g::text, 4, '0'),
    'pass123',
    '555-2' || lpad(g::text, 3, '0'),
    g || ' Residential Avenue, Riverside CA',
    'Buyer',
    -- Every tenth buyer gets NULL, so the reports have to cope with a missing favourite category rather than assuming one is always present.
    CASE WHEN g % 10 = 0 THEN NULL
         ELSE (ARRAY['Clothing','Electronics','Books','Music','Home','Sports','Toys','Garden','Tools','Art'])[1 + (g % 10)]
    END
FROM generate_series(1, 400) AS g;


-- ITEMS -------------------------------------------------------------------------------------------
--
-- 5,000 items spread across the 40 bulk sellers and the 10 categories.
--
-- item_id is omitted, so the sequence created in extensions.sql fills it in -- exactly as items.py will when issue #8 is written. That is also why no setval is needed at the bottom of this file.
--
-- Prices are spread from $5 to $500 rather than clustered, because a price index is only worth measuring against a range query that can actually be selective. Everything priced within a few dollars of everything else would make every range scan return the whole table.

INSERT INTO item (item_name, category, starting_price, image_url, item_condition, description, seller_login, seller_role)
SELECT
    'Bulk Item ' || g,
    (ARRAY['Clothing','Electronics','Books','Music','Home','Sports','Toys','Garden','Tools','Art'])[1 + (g % 10)],
    -- round(x, 2) keeps the value inside NUMERIC(10,2) exactly, so nothing is silently rounded on the way into the column.
    round((5 + random() * 495)::numeric, 2),
    NULL,
    (ARRAY['New','Used - Like New','Used - Good','Used - Fair'])[1 + (g % 4)],
    'Generated row ' || g || ' for index measurement. Not part of the demonstration dataset.',
    -- Modulo spreads items evenly over the 40 sellers, giving each about 125 -- enough that a seller_login index has something to find.
    'bulkseller' || lpad((1 + (g % 40))::text, 4, '0'),
    'Seller'
FROM generate_series(1, 5000) AS g;


-- AUCTIONS ----------------------------------------------------------------------------------------
--
-- One auction per item, for 90% of the bulk items. The remaining 10% stay unsold stock, mirroring seed.sql's Chess Set and Mountain Bike -- issue #8 needs items that have no auction yet.
--
-- This INSERT selects from item rather than from generate_series, because the item_ids were generated by the sequence and are not known in advance. That is the same reason the application uses RETURNING: when the database invents the id, the only way to learn it is to ask.
--
-- seller_login is copied from the item, so an auction is always run by whoever owns the thing being sold. Nothing in the schema enforces that -- item.seller_login and auction.seller_login are separate columns with separate foreign keys -- so it is the loader's job to keep them consistent.
--
-- Every auction starts Active with a current_highest_bid of 0. Both are corrected further down, after the bids exist. Trying to keep the denormalized column in step row by row while inserting bids would mean 25,000 individual updates; doing it once at the end is one statement.

INSERT INTO auction (item_id, seller_login, seller_role, current_highest_bid, auction_status, winner_login, winner_role)
SELECT
    i.item_id,
    i.seller_login,
    'Seller',
    0,
    'Active',
    NULL,
    NULL
FROM item i
WHERE i.seller_login LIKE 'bulkseller%'
  AND i.item_id % 10 <> 0;


-- BIDS --------------------------------------------------------------------------------------------
--
-- Between 1 and 12 bids on each bulk auction -- roughly 25,000 rows, which is where the interesting measurements come from.
--
-- CROSS JOIN LATERAL is what makes the count vary per auction. A plain CROSS JOIN generate_series(1, 12) would put exactly twelve bids on every auction; LATERAL lets the series length be recomputed for each row of the left side, so random() is evaluated per auction rather than once for the whole query.
--
-- TWO INVARIANTS THE WHOLE APPLICATION DEPENDS ON, both preserved here deliberately:
--
--   1. Every bid clears its item's starting_price. bid_amount is starting_price + n*5, and n starts at 1, so even the first bid is $5 above the floor. This is the rule bids.place() enforces, and a bulk dataset that broke it would make the application disagree with its own data.
--   2. Amount and time increase together. n drives both the amount and the timestamp, so the newest bid on an auction is always the largest -- which is what bids.history()'s ORDER BY relies on, and what makes "newest first" and "highest first" the same ordering.
--
-- Buyers are drawn only from bulkbuyer%, and sellers are only bulkseller%, so no generated row can ever be a seller bidding on their own auction.

INSERT INTO bid (auction_id, buyer_login, buyer_role, bid_amount, bid_timestamp)
SELECT
    a.auction_id,
    'bulkbuyer' || lpad((1 + floor(random() * 400))::int::text, 4, '0'),
    'Buyer',
    i.starting_price + (n * 5),
    -- n counts up, so subtracting (200 - n) hours means a larger n is more recent. Spreads the bids across the last eight days or so.
    CURRENT_TIMESTAMP - (interval '1 hour' * (200 - n))
FROM auction a
JOIN item i ON i.item_id = a.item_id
CROSS JOIN LATERAL generate_series(1, 1 + floor(random() * 12)::int) AS n
WHERE a.seller_login LIKE 'bulkseller%';


-- BRING THE DENORMALIZED COLUMN BACK INTO LINE ------------------------------------------------------
--
-- auction.current_highest_bid duplicates the largest bid_amount for that auction. The application keeps the two in step inside a single locked transaction; a bulk load cannot afford that, so it inserts all the bids first and reconciles afterwards in one statement.
--
-- UPDATE ... FROM (subquery) is the PostgreSQL way to update one table from an aggregate over another. The subquery groups every bid by auction and takes the maximum, and the join in the WHERE clause matches each result back to its auction.
--
-- The seeded auctions are excluded, not because updating them would be wrong -- their values already match -- but so this file provably cannot alter a row the demo depends on.

UPDATE auction a
SET current_highest_bid = top.max_amount
FROM (
    SELECT auction_id, MAX(bid_amount) AS max_amount
    FROM bid
    GROUP BY auction_id
) AS top
WHERE top.auction_id = a.auction_id
  AND a.seller_login LIKE 'bulkseller%';


-- CLOSE ABOUT A THIRD OF THEM ------------------------------------------------------------------------
--
-- A dataset where every auction is Active gives the status column no selectivity at all, and half the reports nothing to find. Closing a third produces a realistic mix.
--
-- DISTINCT ON is PostgreSQL's shorthand for "one row per group, and I will tell you which one": it keeps the first row of each auction_id after the ORDER BY, so ordering by bid_amount descending inside each auction picks the highest bidder. Standard SQL needs a window function or a self-join to say the same thing.
--
-- The winner comes from the bid table rather than from current_highest_bid, because the amount alone does not name a person -- exactly the reason auctions.end() runs its own query for this.
--
-- auction_id % 3 = 0 selects the third deterministically rather than randomly, so re-running the file closes the same auctions.

UPDATE auction a
SET auction_status = 'Closed',
    winner_login = w.buyer_login,
    winner_role = 'Buyer'
FROM (
    SELECT DISTINCT ON (auction_id) auction_id, buyer_login
    FROM bid
    ORDER BY auction_id, bid_amount DESC
) AS w
WHERE w.auction_id = a.auction_id
  AND a.seller_login LIKE 'bulkseller%'
  AND a.auction_id % 3 = 0;


-- PAYMENTS ------------------------------------------------------------------------------------------
--
-- Two thirds of the closed auctions get paid for. The remaining third is what gives the won-but-unpaid report real volume instead of the single seeded row.
--
-- payment.auction_id is UNIQUE, so this can only ever write one payment per auction -- which is the schema enforcing "you cannot pay twice" without the application having to check.

INSERT INTO payment (auction_id, buyer_login, buyer_role, amount, payment_status)
SELECT
    a.auction_id,
    a.winner_login,
    'Buyer',
    a.current_highest_bid,
    'Completed'
FROM auction a
WHERE a.seller_login LIKE 'bulkseller%'
  AND a.auction_status = 'Closed'
  AND a.winner_login IS NOT NULL
  AND a.auction_id % 9 <> 0;


-- SHIPMENTS -----------------------------------------------------------------------------------------
--
-- One shipment per completed payment, which is the rule the application enforces: nothing ships before it is paid for. Spread across all three statuses so issue #12 has every state to work against.

INSERT INTO shipment (auction_id, address, shipment_status, tracking_number)
SELECT
    p.auction_id,
    u.address,
    (ARRAY['Pending','Shipped','Delivered'])[1 + (p.auction_id % 3)],
    -- tracking_number stays NULL while a shipment is still Pending, matching what seed.sql does and what the application will do.
    CASE WHEN (p.auction_id % 3) = 0 THEN NULL
         ELSE 'TRK' || lpad(p.auction_id::text, 10, '0')
    END
FROM payment p
JOIN users u ON u.login = p.buyer_login
WHERE p.buyer_login LIKE 'bulkbuyer%';


-- UPDATE THE PLANNER'S STATISTICS ---------------------------------------------------------------------
--
-- ANALYZE must be the last thing this file does, and skipping it would invalidate every measurement taken afterwards.
--
-- PostgreSQL does not choose a plan by looking at the data; it looks at cached statistics about the data -- how many rows a table has, how many distinct values a column holds, how they are distributed. Those statistics are collected by autovacuum on its own schedule, which means that immediately after a bulk load the planner still believes these tables hold the thirty rows seed.sql left behind. It will happily sequential-scan 25,000 bids because it thinks there are eleven.
--
-- Running ANALYZE by hand tells it the truth now rather than in several minutes. If an EXPLAIN ANALYZE ever shows an estimated row count wildly different from the actual, this is the first thing to check.

ANALYZE users;
ANALYZE item;
ANALYZE auction;
ANALYZE bid;
ANALYZE payment;
ANALYZE shipment;


-- WHAT YOU SHOULD SEE AFTER LOADING -------------------------------------------------------------------
--
-- Run these by hand to confirm the load worked and the invariants held. Every one of them should come back clean.
--
--   SELECT COUNT(*) FROM users;    -- 447   (7 seeded + 440 bulk)
--   SELECT COUNT(*) FROM item;     -- 5009  (9 seeded + 5000 bulk)
--   SELECT COUNT(*) FROM auction;  -- ~4507 (7 seeded + ~4500 bulk)
--   SELECT COUNT(*) FROM bid;      -- ~29000
--
--   -- No bid anywhere may be at or below its item's starting price. Must return 0.
--   SELECT COUNT(*) FROM bid b JOIN auction a ON a.auction_id = b.auction_id
--     JOIN item i ON i.item_id = a.item_id WHERE b.bid_amount <= i.starting_price;
--
--   -- Every auction's denormalized high bid must equal its real highest bid. Must return 0.
--   SELECT COUNT(*) FROM auction a JOIN (
--     SELECT auction_id, MAX(bid_amount) AS m FROM bid GROUP BY auction_id) t
--     ON t.auction_id = a.auction_id WHERE a.current_highest_bid <> t.m;
--
--   -- Nobody bid on their own auction. Must return 0.
--   SELECT COUNT(*) FROM bid b JOIN auction a ON a.auction_id = b.auction_id
--     WHERE b.buyer_login = a.seller_login;
--
--   -- The seeded rows are untouched: seller1 still owns auction 1, still Active, still at 62.00.
--   SELECT auction_id, seller_login, auction_status, current_highest_bid FROM auction WHERE auction_id <= 7;
