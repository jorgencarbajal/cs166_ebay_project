"""
Primary key generation.

Nothing in the instructor's schema auto-increments -- every primary key is a plain INT -- so the application invents ids for item, auction, bid, payment, and shipment itself.

next_id() returns MAX(column) + 1 and must be called inside the same transaction as the insert it feeds; otherwise two concurrent inserts can compute the same number and one of them dies on a unique violation. Used by items.py, auctions.py, bids.py, payments.py, and shipments.py. See docs/architecture.md for the sequences alternative we considered.
"""
