"""The Admin's menu: everything a Seller can do, plus user management, item removal, and the reports."""

from .. import reports, ui
from . import buyer, seller


def list_users(session):
    buyer._not_built_yet("Listing all users", 13)


def view_user(session):
    buyer._not_built_yet("Viewing a user", 13)


def change_user_role(session):
    buyer._not_built_yet("Changing a user's role", 14)


def remove_item(session):
    buyer._not_built_yet("Removing an item", 15)


def report_top_bidders(session):
    rows = reports.top_bidders(session)

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


TITLE = "Admin menu"

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
