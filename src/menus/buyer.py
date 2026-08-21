"""
The Buyer's menu: browse, search, bid, pay, track deliveries, edit your profile.

Every Buyer action lives here. Sellers and Admins get all of it too -- seller.py and admin.py start their own lists from this one -- because the spec makes browsing and bidding available to every user, with the role privileges layered on top.

Two names are exported and nothing else. TITLE is the heading, ACTIONS is a list of (key, label, function) triples, and menus/__init__.py does the rest: it draws the menu, calls whichever function was chosen, catches AppError, and loops. There is no while loop in this file and there should never be one.

An action function takes the Session and returns nothing. It calls into the feature modules (auctions.py, bids.py, payments.py), which return data or raise, and it prints the result through ui. That split is the whole architecture: the feature modules never print, and this file never contains business logic or SQL.

Adding an action is two steps. Write the function, then add a triple to ACTIONS.
"""

from .. import ui


# PLACEHOLDERS ---------------------------------------------------------------------------------
#
# The feature modules these will call are still docstrings, so each action says so rather than pretending. Delete _not_built_yet() and its uses as the real functions arrive -- nothing else in the interface needs to change when they do.


def _not_built_yet(feature, issue):
    """Say plainly that a feature is not written yet, and which issue covers it."""
    ui.blank()
    ui.warn(f"{feature} is not built yet -- issue #{issue}.")


def browse_auctions(session):
    _not_built_yet("Browsing auctions", 3)


def search_items(session):
    _not_built_yet("Searching for items", 4)


def view_auction(session):
    _not_built_yet("Auction detail and bid history", 5)


def place_bid(session):
    _not_built_yet("Placing a bid", 7)


def my_bids(session):
    _not_built_yet("Your bid history", 7)


def pay_for_won_auction(session):
    _not_built_yet("Paying for a won auction", 11)


def track_deliveries(session):
    _not_built_yet("Tracking deliveries", 12)


def view_profile(session):
    _not_built_yet("Viewing your profile", 6)


def edit_profile(session):
    _not_built_yet("Editing your profile", 6)


# THE MENU ---------------------------------------------------------------------------------------

TITLE = "Buyer menu"

# Order matters -- this is the order they appear on screen, numbered from 1. Grouped by what someone is trying to do: find something, bid on it, pay for it, then account admin. Log out and Quit are added by run_role_menu() and must not be listed here.
ACTIONS = [
    ("browse", "Browse open auctions", browse_auctions),
    ("search", "Search for an item", search_items),
    ("view", "View an auction in detail", view_auction),
    ("bid", "Place a bid", place_bid),
    ("mybids", "Your bids", my_bids),
    ("pay", "Pay for an auction you won", pay_for_won_auction),
    ("track", "Track a delivery", track_deliveries),
    ("profile", "View your profile", view_profile),
    ("editprofile", "Edit your profile", edit_profile),
]
