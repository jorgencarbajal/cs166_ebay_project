"""The Seller's menu: everything a Buyer can do, plus listings and closing auctions."""

from .. import auctions, ui
from . import buyer


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

    if not ui.confirm(f"Close auction {auction_id}? This cannot be undone", default=False):
        ui.blank()
        ui.info("Cancelled. Nothing was changed.")
        return

    result = auctions.end(session, auction_id)

    ui.blank()

    if result["winner_login"] is None:
        ui.success(f"Auction {auction_id} is closed.")
        ui.info("Nobody bid on it, so there is no winner. The item is still yours to list again.")
    else:
        ui.success(f"Auction {auction_id} is closed. {result['winner_login']} won at ${result['final_price']:,.2f}.")
        ui.info("They can now pay for it from their own menu.")


def mark_shipped(session):
    buyer._not_built_yet("Marking an order shipped", 12)


TITLE = "Seller menu"

ACTIONS = list(buyer.ACTIONS)

ACTIONS += [
    ("list", "List a new item", create_listing),
    ("mylistings", "Your listings", my_listings),
    ("editlisting", "Edit a listing", edit_listing),
    ("startauction", "Put a listing up for auction", start_auction),
    ("endauction", "Close one of your auctions", end_auction),
    ("ship", "Mark a paid order as shipped", mark_shipped),
]
