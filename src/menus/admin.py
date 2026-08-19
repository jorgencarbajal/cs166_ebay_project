"""
The Admin menu.

The buyer actions plus administration: list and search users, inspect one in detail, change a user's role, edit or remove any item, and the reports submenu that monitors auctions.

The reports are where the aggregate SQL lives -- active auctions by value, auctions won but unpaid, paid but unshipped, top bidders, revenue by category -- and they are a graded part of the project rather than a nicety. Calls into users.py, items.py, and auctions.py, all of which enforce the Admin role themselves via require_role.
"""
