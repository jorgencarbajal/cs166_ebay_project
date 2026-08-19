"""
The auction table: browsing, searching, and closing.

The busiest module in the project. It backs browse (paginated listings joined to item), search (filters on name, category, price, and status), the detail view for a single auction, and ending an auction.

Ending is a transaction: find the highest bidder, write winner_login, set auction_status to Closed. Note that current_highest_bid lives on this table but is maintained by bids.py -- the two must stay in sync, which is why bid placement locks the auction row. Auctions have no end time anywhere in the schema; they close only when their seller closes them. Used by every menu.
"""
