# THESE SHOULD BE RAN BEFOR THE DEMO STARTS

# first ensure the db is running
cs166_db_status
cs166_db_start

# load the light demo data
uv run scripts/load_db.py --yes --skip-indexes

# DURING THE DEMO

# run the report sql (Top Bidders)
cs166_psql -d jcarb044_DB -c "
SELECT 
    u.login, 
    u.favorite_category, 
    COUNT(b.bid_id) AS bids_placed, 
    COUNT(DISTINCT b.auction_id) AS auctions_bid_on, 
    MAX(b.bid_amount) AS highest_bid, 
    (SELECT COUNT(*) 
    FROM auction a 
    WHERE a.winner_login = u.login) AS auctions_won 
FROM users u LEFT JOIN bid b ON b.buyer_login = u.login 
WHERE u.role = 'Buyer' 
GROUP BY u.login, u.favorite_category 
ORDER BY bids_placed DESC, highest_bid DESC 
NULLS LAST;"