-- HOW TO TAKE THE MEASUREMENT
--
-- 1. Load the bulk data with no indexes:
--    uv run scripts/load_db.py --yes --bulk --skip-indexes
--
-- 2. Capture the "before" run:
--    cs166_psql -d jcarb044_DB -f sql/tuning_queries.sql > docs/tuning_before.txt
--
-- 3. Build the indexes:
--    cs166_psql -d jcarb044_DB -f sql/indexes.sql
--
-- 4. Capture the "after" run:
--    cs166_psql -d jcarb044_DB -f sql/tuning_queries.sql > docs/tuning_after.txt
--
-- 5. Put the demo dataset back before doing anything else:
--    uv run scripts/load_db.py --yes

\timing on


-- 1. bids.history() -- 

EXPLAIN (ANALYZE, BUFFERS)
SELECT bid_id, buyer_login, bid_amount, bid_timestamp
FROM bid
WHERE auction_id = 500
ORDER BY bid_amount DESC;


-- 2. bids.list_for_buyer() --

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


-- 3. auctions.browse() --

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


-- 4. auctions.search() --

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


-- 5. auctions.search() by name --

EXPLAIN (ANALYZE, BUFFERS)
SELECT a.auction_id, i.item_name, i.category, i.starting_price
FROM auction a
JOIN item i ON i.item_id = a.item_id
WHERE a.auction_status = 'Active'
  AND i.item_name ILIKE '%Item 3%';


-- 6. reports.top_bidders() --

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


-- 7. reports.revenue_by_category() --

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


-- 8. reports.unpaid_wins() --

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


-- 9. reports.active_auctions() --

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


-- 10. HOW BIG IS ALL OF THIS ANYWAY --

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