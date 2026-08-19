"""
The Buyer menu.

Every action available to a logged-in user: browse items, search auctions, view an auction and its bid history, place a bid, pay for a won auction, check shipment status, and view or edit their own profile.

Prompts through ui.py, calls into auctions.py, bids.py, payments.py, shipments.py, and users.py, catches what they raise and renders it. Contains no SQL of its own. Because the spec gives these actions to every user, the seller and admin menus reuse this one rather than duplicating it.
"""
