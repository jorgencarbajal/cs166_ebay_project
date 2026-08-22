"""
The Buyer's menu: browse, search, bid, pay, track deliveries, edit your profile.

Every Buyer action lives here. Sellers and Admins get all of it too -- seller.py and admin.py start their own lists from this one -- because the spec makes browsing and bidding available to every user, with the role privileges layered on top.

Two names are exported and nothing else. TITLE is the heading, ACTIONS is a list of (key, label, function) triples, and menus/__init__.py does the rest: it draws the menu, calls whichever function was chosen, catches AppError, and loops. There is no while loop in this file and there should never be one.

An action function takes the Session and returns nothing. It calls into the feature modules (auctions.py, bids.py, payments.py), which return data or raise, and it prints the result through ui. That split is the whole architecture: the feature modules never print, and this file never contains business logic or SQL.

Adding an action is two steps. Write the function, then add a triple to ACTIONS.
"""

from .. import auctions, ui


# PLACEHOLDERS ---------------------------------------------------------------------------------
#
# The feature modules these will call are still docstrings, so each action says so rather than pretending. Delete _not_built_yet() and its uses as the real functions arrive -- nothing else in the interface needs to change when they do.


def _not_built_yet(feature, issue):
    """Say plainly that a feature is not written yet, and which issue covers it."""
    ui.blank()
    ui.warn(f"{feature} is not built yet -- issue #{issue}.")


# THE REFERENCE ACTION ---------------------------------------------------------------------------
#
# browse_auctions() is the first real action written, so it is the shape every other one copies. Three lines, three jobs: ask the feature module for data, hand the data to ui, say nothing about SQL. Note what is missing -- there is no try/except here. run_role_menu() in menus/__init__.py wraps every action in one, so an AppError raised anywhere below is already handled.


def browse_auctions(session):
    # The feature module does the query and returns a list of dicts. If it raised, the lines below never run.
    rows = auctions.browse(session)

    # Column keys, in display order. ui.page() turns each into a header -- item_name becomes "Item Name" -- and formats the values, so Decimals print as $62.00 and a NULL prints as a dim dash. Pass ("key", "Header") instead of a bare key to override the automatic header.
    columns = [
        ("auction_id", "ID"),
        "item_name",
        "category",
        ("starting_price", "Starting"),
        ("current_highest_bid", "High Bid"),
        ("seller_login", "Seller"),
    ]

    # page() prints the table, and if there is more than one screenful it handles [n]ext / [b]ack / [q]uit itself. An empty list prints "Nothing to show." rather than an empty table.
    ui.page(rows, columns, title="Open auctions")


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
