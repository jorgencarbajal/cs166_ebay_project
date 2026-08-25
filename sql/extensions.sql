DROP SEQUENCE IF EXISTS item_id_seq CASCADE;
DROP SEQUENCE IF EXISTS auction_id_seq CASCADE;
DROP SEQUENCE IF EXISTS bid_id_seq CASCADE;
DROP SEQUENCE IF EXISTS payment_id_seq CASCADE;
DROP SEQUENCE IF EXISTS shipment_id_seq CASCADE;


-- ITEM --

-- Creates a counter object, next number = nextval().
CREATE SEQUENCE item_id_seq;

-- Wires the sequence into the column as its DEFAULT
ALTER TABLE item ALTER COLUMN item_id SET DEFAULT nextval('item_id_seq');

-- Marks the sequence as belonging to that column, CASCADE will clean the sequence up
ALTER SEQUENCE item_id_seq OWNED BY item.item_id;


-- AUCTION --

CREATE SEQUENCE auction_id_seq;
ALTER TABLE auction ALTER COLUMN auction_id SET DEFAULT nextval('auction_id_seq');
ALTER SEQUENCE auction_id_seq OWNED BY auction.auction_id;


-- BID --

CREATE SEQUENCE bid_id_seq;
ALTER TABLE bid ALTER COLUMN bid_id SET DEFAULT nextval('bid_id_seq');
ALTER SEQUENCE bid_id_seq OWNED BY bid.bid_id;


-- PAYMENT --

CREATE SEQUENCE payment_id_seq;
ALTER TABLE payment ALTER COLUMN payment_id SET DEFAULT nextval('payment_id_seq');
ALTER SEQUENCE payment_id_seq OWNED BY payment.payment_id;


-- SHIPMENT --

CREATE SEQUENCE shipment_id_seq;
ALTER TABLE shipment ALTER COLUMN shipment_id SET DEFAULT nextval('shipment_id_seq');
ALTER SEQUENCE shipment_id_seq OWNED BY shipment.shipment_id;