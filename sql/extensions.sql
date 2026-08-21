-- sql/extensions.sql -- our additions to the instructor's schema. Run this immediately AFTER sql/schema.sql, never before, because every statement here depends on the tables already existing.
--
-- WHY THIS FILE EXISTS: the instructor's schema declares every primary key as a plain INT with no auto-increment, which means something has to invent the next id for item, auction, bid, payment, and shipment on every insert. The two options were computing MAX(id) + 1 inside the application, or adding our own sequences. We chose sequences: MAX(id) + 1 has to run inside the same transaction as the insert it feeds, and two transactions can still read the same MAX at the same time and collide on a unique violation, so every insert would need retry logic wrapped around it. A sequence hands out a guaranteed-unique number with no locking and no retries, so the application just omits the id column entirely and lets the database fill it in.
--
-- Spec section 2.3 permits schema extensions as long as they are documented, and section 3 offers extra credit for meaningful ones. This file plus the paragraph above is that documentation.
--
-- Note that `users` gets no sequence. Its primary key is `login`, a VARCHAR the user types in at registration, so there is no number to generate.

-- Dropping first makes this file safe to re-run by hand without erroring on "relation already exists".
-- CASCADE is needed because once a sequence is wired into a column DEFAULT below, that DEFAULT depends on the sequence and a bare DROP would refuse.
DROP SEQUENCE IF EXISTS item_id_seq CASCADE;
DROP SEQUENCE IF EXISTS auction_id_seq CASCADE;
DROP SEQUENCE IF EXISTS bid_id_seq CASCADE;
DROP SEQUENCE IF EXISTS payment_id_seq CASCADE;
DROP SEQUENCE IF EXISTS shipment_id_seq CASCADE;


-- ITEM -------------------------------------------------------------------------------------------

-- Creates a counter object in the database that starts at 1 and hands out 1, 2, 3, ... every time something calls nextval() on it.
CREATE SEQUENCE item_id_seq;

-- Wires the sequence into the column as its DEFAULT, so an INSERT that does not mention item_id gets the next number automatically. This is exactly what SERIAL does in Postgres under the hood -- we are writing out by hand what SERIAL would have generated, because we are not allowed to edit the instructor's CREATE TABLE.
ALTER TABLE item ALTER COLUMN item_id SET DEFAULT nextval('item_id_seq');

-- Marks the sequence as belonging to that column, which means schema.sql's DROP TABLE ... CASCADE will clean the sequence up too instead of leaving orphans behind in the database.
ALTER SEQUENCE item_id_seq OWNED BY item.item_id;


-- AUCTION ----------------------------------------------------------------------------------------

CREATE SEQUENCE auction_id_seq;
ALTER TABLE auction ALTER COLUMN auction_id SET DEFAULT nextval('auction_id_seq');
ALTER SEQUENCE auction_id_seq OWNED BY auction.auction_id;


-- BID --------------------------------------------------------------------------------------------

CREATE SEQUENCE bid_id_seq;
ALTER TABLE bid ALTER COLUMN bid_id SET DEFAULT nextval('bid_id_seq');
ALTER SEQUENCE bid_id_seq OWNED BY bid.bid_id;


-- PAYMENT ----------------------------------------------------------------------------------------

CREATE SEQUENCE payment_id_seq;
ALTER TABLE payment ALTER COLUMN payment_id SET DEFAULT nextval('payment_id_seq');
ALTER SEQUENCE payment_id_seq OWNED BY payment.payment_id;


-- SHIPMENT ---------------------------------------------------------------------------------------

CREATE SEQUENCE shipment_id_seq;
ALTER TABLE shipment ALTER COLUMN shipment_id SET DEFAULT nextval('shipment_id_seq');
ALTER SEQUENCE shipment_id_seq OWNED BY shipment.shipment_id;


-- HOW THE APPLICATION USES THIS ------------------------------------------------------------------
--
-- Before (what MAX(id) + 1 would have forced us to write):
--     INSERT INTO bid (bid_id, auction_id, buyer_login, bid_amount) VALUES (%s, %s, %s, %s)
--     ...with a separate SELECT COALESCE(MAX(bid_id), 0) + 1 FROM bid beforehand, in the same transaction, and a retry if it collided.
--
-- After (what we actually write):
--     INSERT INTO bid (auction_id, buyer_login, bid_amount) VALUES (%s, %s, %s) RETURNING bid_id
--
-- RETURNING hands the generated id straight back on the same round trip, so the application never has to ask what number it just got. Every insert in items.py, auctions.py, bids.py, payments.py, and shipments.py follows that shape.
--
-- ONE THING TO REMEMBER WHEN SEEDING: if sql/seed.sql ever inserts rows with explicit ids -- for example generate_series writing item_id 1 through 5000 directly -- the sequences will not know about them and will still be sitting at 1, so the first item created through the app would collide. Fix it by resetting each sequence past the seeded data at the end of seed.sql, like this:
--     SELECT setval('item_id_seq', (SELECT COALESCE(MAX(item_id), 0) FROM item));
-- The cleanest alternative is for seed.sql to omit the id columns too and let these sequences number the seed rows as well, which sidesteps the problem entirely.
