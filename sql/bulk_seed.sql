SELECT setseed(0.166);


DELETE FROM shipment WHERE auction_id IN (SELECT auction_id FROM auction WHERE seller_login LIKE 'bulkseller%');
DELETE FROM payment  WHERE auction_id IN (SELECT auction_id FROM auction WHERE seller_login LIKE 'bulkseller%');
DELETE FROM bid      WHERE buyer_login LIKE 'bulkbuyer%';
DELETE FROM auction  WHERE seller_login LIKE 'bulkseller%';
DELETE FROM item     WHERE seller_login LIKE 'bulkseller%';
DELETE FROM users    WHERE login LIKE 'bulk%';


INSERT INTO users (login, password, phone_num, address, role, favorite_category)
SELECT
    'bulkseller' || lpad(g::text, 4, '0'),
    'pass123',
    '555-1' || lpad(g::text, 3, '0'),
    g || ' Warehouse Row, Riverside CA',
    'Seller',
    (ARRAY['Clothing','Electronics','Books','Music','Home','Sports','Toys','Garden','Tools','Art'])[1 + (g % 10)]
FROM generate_series(1, 40) AS g;

INSERT INTO users (login, password, phone_num, address, role, favorite_category)
SELECT
    'bulkbuyer' || lpad(g::text, 4, '0'),
    'pass123',
    '555-2' || lpad(g::text, 3, '0'),
    g || ' Residential Avenue, Riverside CA',
    'Buyer',
    CASE WHEN g % 10 = 0 THEN NULL
         ELSE (ARRAY['Clothing','Electronics','Books','Music','Home','Sports','Toys','Garden','Tools','Art'])[1 + (g % 10)]
    END
FROM generate_series(1, 400) AS g;


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


UPDATE auction a
SET current_highest_bid = top.max_amount
FROM (
    SELECT auction_id, MAX(bid_amount) AS max_amount
    FROM bid
    GROUP BY auction_id
) AS top
WHERE top.auction_id = a.auction_id
  AND a.seller_login LIKE 'bulkseller%';


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


ANALYZE users;
ANALYZE item;
ANALYZE auction;
ANALYZE bid;
ANALYZE payment;
ANALYZE shipment;