"""
The bid table: placing bids and reading bid history.

The most constraint-heavy module here. A bid must beat both auction.current_highest_bid and the item's starting_price, the auction must still be Active, and a seller may not bid on their own auction -- each failure raises a specific error from errors.py.

Placing a bid is one transaction that locks the auction row with SELECT ... FOR UPDATE, inserts into bid, and updates auction.current_highest_bid. That denormalized column is the reason the lock exists: two buyers reading the same stale high bid could otherwise both pass validation. Used by menus/buyer.py, and its history() feeds the auction detail view in auctions.py.
"""
