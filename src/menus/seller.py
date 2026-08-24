"""
The Seller's menu: everything a Buyer can do, plus listings and closing auctions.

A Seller is a Buyer with extra powers, not a different kind of user, so ACTIONS below starts as a copy of buyer.ACTIONS and appends to it. That is why browsing and bidding appear here without being written twice -- fix a bug in buyer.browse_auctions() and it is fixed on this menu too.

Exports TITLE and ACTIONS and nothing else. menus/__init__.py draws the menu, calls the chosen function, catches AppError, and loops. No while loop belongs in this file.

Owner: this is one of the three role files, split so three people can work without colliding. The feature modules it calls -- items.py, auctions.py -- are the other half of the same slice.
"""

from .. import auctions, ui
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
    auction_id = ui.prompt_int("Auction id to close", minimum=1)

    # Closing is irreversible -- there is no reopen anywhere in the schema or the spec -- so ask before doing it. This is the only confirm in the project so far, and it is here rather than in auctions.end() because asking a question is a terminal job and the feature modules do not know a terminal exists.
    # default=False means a bare Enter cancels, which is the safe way round for something that cannot be undone.
    if not ui.confirm(f"Close auction {auction_id}? This cannot be undone", default=False):
        ui.blank()
        ui.info("Cancelled. Nothing was changed.")
        return

    # Every refusal -- not your auction, already closed, no such auction -- raises out of here and is caught by run_role_menu(). Nothing to handle in this function.
    result = auctions.end(session, auction_id)

    ui.blank()

    # Two genuinely different outcomes, so they get two different sentences rather than one with a blank in it. winner_login is None when nobody bid, which is a normal way for an auction to end and not a failure worth an error colour.
    if result["winner_login"] is None:
        ui.success(f"Auction {auction_id} is closed.")
        ui.info("Nobody bid on it, so there is no winner. The item is still yours to list again.")
    else:
        ui.success(f"Auction {auction_id} is closed. {result['winner_login']} won at ${result['final_price']:,.2f}.")
        ui.info("They can now pay for it from their own menu.")


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
