"""
The Seller menu.

The buyer actions plus the seller privileges: create a listing, review and edit their own listings, end an auction, and create or update a shipment once its payment has completed.

Prompts through ui.py and calls into items.py, auctions.py, and shipments.py. Ownership is verified inside those modules, not here -- this file only decides what to show and how to display the result. Ending an auction is irreversible, so it confirms first.
"""
