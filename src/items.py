"""
The item table: listings.

Sellers create items and update their own; admins can edit or remove any of them. Every function that modifies an item verifies ownership and raises NotAuthorized when it fails, rather than relying on the menu to have hidden the option.

Creating a listing is not just an item -- items.py and auctions.py are called together in one transaction, because an item with no auction is unreachable from every part of the UI. Deleting is restricted by the schema: auction references item with ON DELETE RESTRICT, so a delete fails while an auction exists. Used by menus/seller.py and menus/admin.py.
"""
