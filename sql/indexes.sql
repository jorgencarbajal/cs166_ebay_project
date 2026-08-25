DROP INDEX IF EXISTS idx_bid_auction_amount;
DROP INDEX IF EXISTS idx_bid_buyer;
DROP INDEX IF EXISTS idx_auction_active;
DROP INDEX IF EXISTS idx_auction_winner;
DROP INDEX IF EXISTS idx_auction_seller;
DROP INDEX IF EXISTS idx_item_category;
DROP INDEX IF EXISTS idx_item_starting_price;
DROP INDEX IF EXISTS idx_item_seller;


CREATE INDEX idx_bid_auction_amount ON bid (auction_id, bid_amount DESC);


CREATE INDEX idx_bid_buyer ON bid (buyer_login);


CREATE INDEX idx_auction_active ON auction (auction_id) WHERE auction_status = 'Active';


CREATE INDEX idx_auction_winner ON auction (winner_login);


CREATE INDEX idx_auction_seller ON auction (seller_login);
CREATE INDEX idx_item_seller ON item (seller_login);


CREATE INDEX idx_item_category ON item (category);


CREATE INDEX idx_item_starting_price ON item (starting_price);


ANALYZE item;
ANALYZE auction;
ANALYZE bid;