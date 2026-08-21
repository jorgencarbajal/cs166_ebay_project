"""
The Seller's menu: everything a Buyer can do, plus listings and closing auctions.

A Seller is a Buyer with extra powers, not a different kind of user, so ACTIONS below starts as a copy of buyer.ACTIONS and appends to it. That is why browsing and bidding appear here without being written twice -- fix a bug in buyer.browse_auctions() and it is fixed on this menu too.

Exports TITLE and ACTIONS and nothing else. menus/__init__.py draws the menu, calls the chosen function, catches AppError, and loops. No while loop belongs in this file.

Owner: this is one of the three role files, split so three people can work without colliding. The feature modules it calls -- items.py, auctions.py -- are the other half of the same slice.
"""

from .. import ui
from . import buyer


# PLACEHOLDERS -----------------------------------------------------------------------------------
#
# items.py and auctions.py are still docstrings, so each action says which issue covers it rather than pretending to work. Replace these as the real functions land; ACTIONS below does not need to change, only the bodies.


def create_listing(session):
    buyer._not_built_yet("Creating a listing", 8)


def my_listings(session):
    buyer._not_built_yet("Your listings", 9)


def edit_listing(session):
    buyer._not_built_yet("Editing a listing", 9)


def start_auction(session):
    buyer._not_built_yet("Starting an auction", 8)


def end_auction(session):
    buyer._not_built_yet("Ending an auction", 10)


def mark_shipped(session):
    buyer._not_built_yet("Marking an order shipped", 12)


# THE MENU ---------------------------------------------------------------------------------------

TITLE = "Seller menu"

# list(...) makes a copy rather than an alias. Without it, the += below would append to buyer.ACTIONS itself and the Buyer menu would sprout Seller options -- a bug that would look inexplicable on screen.
ACTIONS = list(buyer.ACTIONS)

# Seller powers go after the shared Buyer actions, so the numbering of the common options stays the same whichever menu you are on. That consistency is worth more than perfect grouping during a live demo.
ACTIONS += [
    ("list", "List a new item", create_listing),
    ("mylistings", "Your listings", my_listings),
    ("editlisting", "Edit a listing", edit_listing),
    ("startauction", "Put a listing up for auction", start_auction),
    ("endauction", "Close one of your auctions", end_auction),
    ("ship", "Mark a paid order as shipped", mark_shipped),
]
