"""
The Admin's menu: everything a Seller can do, plus user management, item removal, and the reports.

An Admin outranks a Seller, who outranks a Buyer, so ACTIONS below starts from seller.ACTIONS -- which already starts from buyer.ACTIONS -- and appends. Each role's menu is therefore the one below it plus its own powers, written once.

Exports TITLE and ACTIONS and nothing else. menus/__init__.py draws the menu, calls the chosen function, catches AppError, and loops.

The four reports (issue #16) are the most visible thing on this menu during a demo: they are the §6 queries that show the database being used for more than row lookups, and they render through ui.page() like every other table.
"""

from .. import reports, ui
from . import buyer, seller


# PLACEHOLDERS -----------------------------------------------------------------------------------
#
# users.py, items.py, and auctions.py are still docstrings. Each action names the issue that will replace it.


def list_users(session):
    buyer._not_built_yet("Listing all users", 13)


def view_user(session):
    buyer._not_built_yet("Viewing a user", 13)


def change_user_role(session):
    buyer._not_built_yet("Changing a user's role", 14)


def remove_item(session):
    buyer._not_built_yet("Removing an item", 15)


# THE FOUR REPORTS -------------------------------------------------------------------------------
#
# All four are the same three lines -- ask reports.py, hand the rows to ui.page(), name the columns. The queries themselves are the interesting part and they all live in src/reports.py; nothing below knows any SQL.


def report_top_bidders(session):
    rows = reports.top_bidders(session)

    # highest_bid comes back as None for a Buyer who has never bid, which is what the LEFT JOIN in the query is for. ui.page() renders a None as a dim dash, so the empty cell reads as "nothing here" rather than looking like a bug.
    ui.page(
        rows,
        [
            ("login", "Buyer"),
            ("favorite_category", "Favourite"),
            ("bids_placed", "Bids"),
            ("auctions_bid_on", "Auctions"),
            ("highest_bid", "Highest Bid"),
            ("auctions_won", "Won"),
        ],
        title="Top bidders",
    )


def report_revenue_by_category(session):
    rows = reports.revenue_by_category(session)

    ui.page(
        rows,
        [
            ("category", "Category"),
            ("items_sold", "Sold"),
            ("revenue", "Revenue"),
            ("average_sale", "Average"),
            ("largest_sale", "Largest"),
        ],
        title="Revenue by category",
    )


def report_unpaid_wins(session):
    rows = reports.unpaid_wins(session)

    # An empty result is the good outcome here -- it means everybody has paid -- so say so rather than letting ui.page() print its neutral "Nothing to show." for something worth celebrating.
    if not rows:
        ui.blank()
        ui.success("Every closed auction has been paid for.")
        return

    ui.page(
        rows,
        [
            ("auction_id", "Auction"),
            "item_name",
            ("winner_login", "Winner"),
            ("amount_owed", "Owed"),
            ("seller_login", "Seller"),
        ],
        title="Won but unpaid",
    )


def report_active_auctions(session):
    rows = reports.active_auctions(session)

    # Bids and Bidders sit next to each other deliberately: three bids from one buyer and three bids from three buyers look identical until both columns are visible.
    ui.page(
        rows,
        [
            ("auction_id", "ID"),
            "item_name",
            ("category", "Category"),
            ("starting_price", "Starting"),
            ("current_highest_bid", "High Bid"),
            ("bids_placed", "Bids"),
            ("bidders", "Bidders"),
        ],
        title="Active auctions by high bid",
    )


# THE MENU ---------------------------------------------------------------------------------------

TITLE = "Admin menu"

# Copied, not aliased -- see the note in seller.py. This copies the Seller list, which is itself already a copy of the Buyer list, so nothing here can reach back and modify either.
ACTIONS = list(seller.ACTIONS)

ACTIONS += [
    ("users", "List all users", list_users),
    ("viewuser", "View a user", view_user),
    ("role", "Change a user's role", change_user_role),
    ("rmitem", "Remove an item", remove_item),
    ("rptbidders", "Report: top bidders", report_top_bidders),
    ("rptrevenue", "Report: revenue by category", report_revenue_by_category),
    ("rptunpaid", "Report: won but unpaid", report_unpaid_wins),
    ("rptactive", "Report: active auctions by high bid", report_active_auctions),
]
