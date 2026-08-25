DELETE FROM shipment;
DELETE FROM payment;
DELETE FROM bid;
DELETE FROM auction;
DELETE FROM item;
DELETE FROM users;


-- USERS --

INSERT INTO users (login, password, phone_num, address, role, favorite_category) VALUES
    ('admin1',  'pass123', '555-0100', '1 Registry Way, Riverside CA',   'Admin',  'Electronics'),
    ('seller1', 'pass123', '555-0101', '22 Market Street, Riverside CA', 'Seller', 'Electronics'),
    ('seller2', 'pass123', '555-0102', '9 Warehouse Road, Riverside CA', 'Seller', 'Books'),
    ('buyer1',  'pass123', '555-0201', '404 Elm Street, Riverside CA',   'Buyer',  'Books'),
    ('buyer2',  'pass123', '555-0202', '77 Oak Avenue, Riverside CA',    'Buyer',  'Music'),
    ('buyer3',  'pass123', '555-0203', '15 Pine Court, Riverside CA',    'Buyer',  NULL),
    ('newbie1', 'pass123', '555-0204', '3 Sycamore Lane, Riverside CA',  'Buyer',  'Sports');


-- ITEMS --

INSERT INTO item (item_id, item_name, category, starting_price, image_url, item_condition, description, seller_login, seller_role) VALUES
    (1, 'Vintage Leather Jacket', 'Clothing',    45.00,  NULL, 'Used - Good',      'Brown leather, size medium, light wear at the cuffs.',        'seller1', 'Seller'),
    (2, 'Mechanical Keyboard',    'Electronics', 60.00,  NULL, 'Used - Like New',  '87-key tenkeyless, brown switches, original box included.',   'seller1', 'Seller'),
    (3, 'First Edition Dune',     'Books',       120.00, NULL, 'Used - Fair',      '1965 hardcover, dust jacket torn, binding tight.',            'seller2', 'Seller'),
    (4, 'Acoustic Guitar',        'Music',       200.00, NULL, 'Used - Good',      'Dreadnought body, spruce top, hard case included.',           'seller2', 'Seller'),
    (5, 'Film Camera',            'Electronics', 85.00,  NULL, 'Used - Good',      '35mm SLR with 50mm lens, meter tested and working.',          'seller1', 'Seller'),
    (6, 'Wool Rug',               'Home',        150.00, NULL, 'Used - Like New',  'Hand-knotted, 5 by 8 feet, no stains or fading.',             'seller2', 'Seller'),
    (7, 'Chess Set',              'Home',        30.00,  NULL, 'New',              'Weighted pieces, folding wooden board.',                      'seller1', 'Seller'),
    (8, 'Mountain Bike',          'Sports',      250.00, NULL, 'Used - Good',      '29 inch wheels, hydraulic disc brakes, recently serviced.',   'seller2', 'Seller'),
    (9, 'Desk Lamp',              'Home',        25.00,  NULL, 'Used - Good',      'Adjustable arm, warm LED bulb included.',                     'seller1', 'Seller');


-- AUCTIONS --

INSERT INTO auction (auction_id, item_id, seller_login, seller_role, current_highest_bid, auction_status, winner_login, winner_role) VALUES
    (1, 1, 'seller1', 'Seller', 62.00,  'Active', NULL,     NULL),
    (2, 2, 'seller1', 'Seller', 78.50,  'Active', NULL,     NULL),
    (3, 3, 'seller2', 'Seller', 0.00,   'Active', NULL,     NULL),
    (4, 4, 'seller2', 'Seller', 245.00, 'Closed', 'buyer2', 'Buyer'),
    (5, 5, 'seller1', 'Seller', 96.00,  'Closed', 'buyer1', 'Buyer'),
    (6, 6, 'seller2', 'Seller', 165.00, 'Active', NULL,     NULL),
    (7, 9, 'seller1', 'Seller', 40.00,  'Closed', 'buyer3', 'Buyer');


-- BIDS --

INSERT INTO bid (bid_id, auction_id, buyer_login, buyer_role, bid_amount, bid_timestamp) VALUES
    -- Auction 1 -- starting price 45.00, three bids, buyer1 currently leading.
    (1,  1, 'buyer1', 'Buyer', 50.00,  CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (2,  1, 'buyer2', 'Buyer', 55.00,  CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (3,  1, 'buyer1', 'Buyer', 62.00,  CURRENT_TIMESTAMP - INTERVAL '2 days'),

    -- Auction 2 -- starting price 60.00, buyer3 currently leading.
    (4,  2, 'buyer2', 'Buyer', 65.00,  CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (5,  2, 'buyer3', 'Buyer', 78.50,  CURRENT_TIMESTAMP - INTERVAL '1 day'),

    -- Auction 4 -- closed, buyer2 won at 245.00.
    (6,  4, 'buyer1', 'Buyer', 210.00, CURRENT_TIMESTAMP - INTERVAL '12 days'),
    (7,  4, 'buyer2', 'Buyer', 245.00, CURRENT_TIMESTAMP - INTERVAL '10 days'),

    -- Auction 5 -- closed, buyer1 won at 96.00 and has not paid.
    (8,  5, 'buyer1', 'Buyer', 96.00,  CURRENT_TIMESTAMP - INTERVAL '8 days'),

    -- Auction 6 -- starting price 150.00, buyer2 currently leading.
    (9,  6, 'buyer3', 'Buyer', 155.00, CURRENT_TIMESTAMP - INTERVAL '6 hours'),
    (10, 6, 'buyer2', 'Buyer', 165.00, CURRENT_TIMESTAMP - INTERVAL '2 hours'),

    -- Auction 7 -- closed, buyer3 won at 40.00 and has paid.
    (11, 7, 'buyer3', 'Buyer', 40.00,  CURRENT_TIMESTAMP - INTERVAL '9 days');


-- PAYMENTS --

INSERT INTO payment (payment_id, auction_id, buyer_login, buyer_role, amount, payment_status) VALUES
    (1, 4, 'buyer2', 'Buyer', 245.00, 'Completed'),
    (2, 7, 'buyer3', 'Buyer', 40.00,  'Completed');


-- SHIPMENTS --

INSERT INTO shipment (shipment_id, auction_id, address, shipment_status, tracking_number) VALUES
    (1, 4, '77 Oak Avenue, Riverside CA', 'Delivered', 'TRK1000000004'),
    -- Paid but not yet dispatched. tracking_number stays NULL until it ships.
    (2, 7, '15 Pine Court, Riverside CA', 'Pending',   NULL);


-- RESET THE SEQUENCES --

SELECT setval('item_id_seq',     (SELECT COALESCE(MAX(item_id), 0)     + 1 FROM item),     false);
SELECT setval('auction_id_seq',  (SELECT COALESCE(MAX(auction_id), 0)  + 1 FROM auction),  false);
SELECT setval('bid_id_seq',      (SELECT COALESCE(MAX(bid_id), 0)      + 1 FROM bid),      false);
SELECT setval('payment_id_seq',  (SELECT COALESCE(MAX(payment_id), 0)  + 1 FROM payment),  false);
SELECT setval('shipment_id_seq', (SELECT COALESCE(MAX(shipment_id), 0) + 1 FROM shipment), false);
