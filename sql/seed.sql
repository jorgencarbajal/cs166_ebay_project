-- sql/seed.sql -- a small starter dataset, ours. Run by scripts/load_db.py immediately after sql/extensions.sql.
--
-- WHAT THIS IS AND IS NOT: this is the *development* dataset -- just enough rows, in just enough different states, that every feature has something to work against on the day it is written. It is deliberately tiny and deliberately readable. The real dataset, with the volume issue #17 needs before an index measurement means anything, comes later and replaces the row data below without changing its shape.
--
-- WHY IT EXISTS AT ALL: without it, whoever writes "browse auctions" has nothing to browse, and cannot create anything either, because listing an item is somebody else's issue. Every feature would be blocked on a different feature. Thirty rows removes that entirely.
--
-- EVERY LOGIN IS PREDICTABLE AND EVERY PASSWORD IS THE SAME: admin1, seller1, seller2, buyer1, buyer2, buyer3, newbie1, all with the password 'pass123'. Nobody should have to grep the database for a login in the middle of a demo.
--
-- PASSWORDS ARE PLAIN TEXT, on purpose. The instructor's schema stores them as VARCHAR and the application compares them directly, so hashing here would lock us out of every account below. Documented as a limitation in the report.
--
-- IDS ARE EXPLICIT HERE, unlike everywhere else in the project. The application always omits ids and lets the sequences fill them in, but a seed file has to reference its own rows -- auction 4 has to point at item 4 -- and hard-coded numbers are far easier to read and correct than a chain of RETURNING values. The consequence is that the sequences do not know these rows exist and would hand out 1 again, colliding on the first insert through the app. The setval block at the very bottom fixes that and MUST stay last.


-- CLEAN SLATE ------------------------------------------------------------------------------------
--
-- Not needed when load_db.py runs the whole chain, because schema.sql has already dropped and recreated every table by then. This is here so the file can also be run on its own -- cs166_psql -d jcarb044_DB -f sql/seed.sql -- to reset the data without rebuilding the schema.
--
-- Order matters: children before parents, or the foreign keys refuse. It is the reverse of the order the inserts appear in below.

DELETE FROM shipment;
DELETE FROM payment;
DELETE FROM bid;
DELETE FROM auction;
DELETE FROM item;
DELETE FROM users;


-- USERS ------------------------------------------------------------------------------------------
--
-- Seven accounts covering every role. Note newbie1 at the bottom: a Buyer who owns no items and has placed no bids, which makes them the one account that can actually be promoted to Seller. Every other Buyer here has bids, and issue #14 refuses a role change for anyone with dependent rows -- the (login, role) foreign keys cascade on update and would land the child rows on the wrong side of their pinning CHECK.
--
-- favorite_category is the only nullable column on this table. buyer3 leaves it NULL so the browse and profile screens have a real NULL to render.

INSERT INTO users (login, password, phone_num, address, role, favorite_category) VALUES
    ('admin1',  'pass123', '555-0100', '1 Registry Way, Riverside CA',   'Admin',  'Electronics'),
    ('seller1', 'pass123', '555-0101', '22 Market Street, Riverside CA', 'Seller', 'Electronics'),
    ('seller2', 'pass123', '555-0102', '9 Warehouse Road, Riverside CA', 'Seller', 'Books'),
    ('buyer1',  'pass123', '555-0201', '404 Elm Street, Riverside CA',   'Buyer',  'Books'),
    ('buyer2',  'pass123', '555-0202', '77 Oak Avenue, Riverside CA',    'Buyer',  'Music'),
    ('buyer3',  'pass123', '555-0203', '15 Pine Court, Riverside CA',    'Buyer',  NULL),
    -- No items, no bids, no payments. Kept clean so the "promote a Buyer to Seller" demo has something that works.
    ('newbie1', 'pass123', '555-0204', '3 Sycamore Lane, Riverside CA',  'Buyer',  'Sports');


-- ITEMS ------------------------------------------------------------------------------------------
--
-- Nine listings across six categories, so category filtering and the revenue-by-category report have more than one group to work with.
--
-- Items 7 and 8 have no auction. That is not an oversight: a listing and an auction are separate things in this schema, so a Seller needs an un-auctioned item sitting there to demonstrate putting one up for auction.
--
-- seller_role is written out even though the column defaults to 'Seller', because it is half of the foreign key into users(login, role) and spelling it out is what makes the pairing obvious to anyone reading this file.

INSERT INTO item (item_id, item_name, category, starting_price, image_url, item_condition, description, seller_login, seller_role) VALUES
    (1, 'Vintage Leather Jacket', 'Clothing',    45.00,  NULL, 'Used - Good',      'Brown leather, size medium, light wear at the cuffs.',        'seller1', 'Seller'),
    (2, 'Mechanical Keyboard',    'Electronics', 60.00,  NULL, 'Used - Like New',  '87-key tenkeyless, brown switches, original box included.',   'seller1', 'Seller'),
    (3, 'First Edition Dune',     'Books',       120.00, NULL, 'Used - Fair',      '1965 hardcover, dust jacket torn, binding tight.',            'seller2', 'Seller'),
    (4, 'Acoustic Guitar',        'Music',       200.00, NULL, 'Used - Good',      'Dreadnought body, spruce top, hard case included.',           'seller2', 'Seller'),
    (5, 'Film Camera',            'Electronics', 85.00,  NULL, 'Used - Good',      '35mm SLR with 50mm lens, meter tested and working.',          'seller1', 'Seller'),
    (6, 'Wool Rug',               'Home',        150.00, NULL, 'Used - Like New',  'Hand-knotted, 5 by 8 feet, no stains or fading.',             'seller2', 'Seller'),
    -- No auction on this one -- available for a Seller to put up.
    (7, 'Chess Set',              'Home',        30.00,  NULL, 'New',              'Weighted pieces, folding wooden board.',                      'seller1', 'Seller'),
    -- No auction on this one either.
    (8, 'Mountain Bike',          'Sports',      250.00, NULL, 'Used - Good',      '29 inch wheels, hydraulic disc brakes, recently serviced.',   'seller2', 'Seller'),
    (9, 'Desk Lamp',              'Home',        25.00,  NULL, 'Used - Good',      'Adjustable arm, warm LED bulb included.',                     'seller1', 'Seller');


-- AUCTIONS ---------------------------------------------------------------------------------------
--
-- Seven auctions, chosen so that every state a feature has to handle already exists in the data:
--
--   1  Active, several bids          the ordinary case
--   2  Active, several bids          a second ordinary case, different seller pattern
--   3  Active, NO bids at all        current_highest_bid is 0, so bidding has to fall back to the item's starting_price
--   4  Closed, won, paid, delivered  the complete happy path from end to end
--   5  Closed, won, NOT paid         what the won-but-unpaid report in issue #16 is looking for
--   6  Active, several bids          gives the browse screen enough rows to be worth paginating
--   7  Closed, won, paid, unshipped  a shipment still sitting at Pending, so the Seller has something to mark Shipped
--
-- current_highest_bid is denormalized -- it duplicates the highest row in bid -- so every value here has to match the bids below exactly. If you edit a bid, edit this too. Keeping those two in step is the entire reason issue #7 wraps bidding in a transaction.
--
-- winner_login is NULL on every Active auction. It is filled in only when the seller closes the auction.

INSERT INTO auction (auction_id, item_id, seller_login, seller_role, current_highest_bid, auction_status, winner_login, winner_role) VALUES
    (1, 1, 'seller1', 'Seller', 62.00,  'Active', NULL,     NULL),
    (2, 2, 'seller1', 'Seller', 78.50,  'Active', NULL,     NULL),
    -- Nothing bid yet, so the high bid sits at the column default of 0.
    (3, 3, 'seller2', 'Seller', 0.00,   'Active', NULL,     NULL),
    (4, 4, 'seller2', 'Seller', 245.00, 'Closed', 'buyer2', 'Buyer'),
    -- Won but never paid for. This is the row the unpaid report has to find.
    (5, 5, 'seller1', 'Seller', 96.00,  'Closed', 'buyer1', 'Buyer'),
    (6, 6, 'seller2', 'Seller', 165.00, 'Active', NULL,     NULL),
    (7, 9, 'seller1', 'Seller', 40.00,  'Closed', 'buyer3', 'Buyer');


-- BIDS -------------------------------------------------------------------------------------------
--
-- Eleven bids. Every one clears its item's starting_price, and every auction's last bid matches the current_highest_bid recorded above -- check both if you change anything here.
--
-- bid_timestamp is the only timestamp in the whole schema, so it is what every "newest first" ordering in the application sorts on. The offsets below are relative to whenever the seed is loaded, which keeps them sensible no matter when that happens, and they are spaced so that within one auction the bids climb in both amount and time.

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

-- Auction 3 has no bids on purpose. Do not add one -- it is the only row that exercises the "no bids yet" path.


-- PAYMENTS ---------------------------------------------------------------------------------------
--
-- Two payments, both Completed, each for a closed auction whose winner paid. The amount equals the winning bid.
--
-- Auction 5 is deliberately absent: buyer1 won it and never paid. payment.auction_id is UNIQUE, which is what stops anyone paying twice, and it is also what makes "closed auctions with no payment row" a simple LEFT JOIN for the report.

INSERT INTO payment (payment_id, auction_id, buyer_login, buyer_role, amount, payment_status) VALUES
    (1, 4, 'buyer2', 'Buyer', 245.00, 'Completed'),
    (2, 7, 'buyer3', 'Buyer', 40.00,  'Completed');


-- SHIPMENTS --------------------------------------------------------------------------------------
--
-- One shipment per completed payment, which is the rule the application enforces: nothing ships before it is paid for.
--
-- The two are at different points in the Pending -> Shipped -> Delivered flow on purpose. Auction 4 is finished; auction 7 is still Pending, so seller1 has something to mark as Shipped without any setup.
--
-- The address is copied from the winner's users row rather than joined at read time, because a delivery address has to record where the parcel was actually sent even if the buyer moves house later.

INSERT INTO shipment (shipment_id, auction_id, address, shipment_status, tracking_number) VALUES
    (1, 4, '77 Oak Avenue, Riverside CA', 'Delivered', 'TRK1000000004'),
    -- Paid but not yet dispatched. tracking_number stays NULL until it ships.
    (2, 7, '15 Pine Court, Riverside CA', 'Pending',   NULL);


-- RESET THE SEQUENCES ----------------------------------------------------------------------------
--
-- MUST BE LAST, and must not be deleted.
--
-- Every INSERT above supplied its own id, which means the sequences created in sql/extensions.sql never advanced -- they are all still sitting at 1. The first item created through the running application would ask for nextval('item_id_seq'), get 1, and collide with the Vintage Leather Jacket.
--
-- setval() moves each sequence past the data. COALESCE(MAX(...), 0) handles a table that ended up empty, and the third argument -- false -- means "the next call to nextval() returns exactly this number", which is why each one is MAX + 1 rather than MAX.

SELECT setval('item_id_seq',     (SELECT COALESCE(MAX(item_id), 0)     + 1 FROM item),     false);
SELECT setval('auction_id_seq',  (SELECT COALESCE(MAX(auction_id), 0)  + 1 FROM auction),  false);
SELECT setval('bid_id_seq',      (SELECT COALESCE(MAX(bid_id), 0)      + 1 FROM bid),      false);
SELECT setval('payment_id_seq',  (SELECT COALESCE(MAX(payment_id), 0)  + 1 FROM payment),  false);
SELECT setval('shipment_id_seq', (SELECT COALESCE(MAX(shipment_id), 0) + 1 FROM shipment), false);
