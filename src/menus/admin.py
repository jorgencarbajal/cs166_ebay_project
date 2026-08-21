"""
The Admin's menu: everything a Seller can do, plus user management, item removal, and the reports.

An Admin outranks a Seller, who outranks a Buyer, so ACTIONS below starts from seller.ACTIONS -- which already starts from buyer.ACTIONS -- and appends. Each role's menu is therefore the one below it plus its own powers, written once.

Exports TITLE and ACTIONS and nothing else. menus/__init__.py draws the menu, calls the chosen function, catches AppError, and loops.

The four reports (issue #16) are the most visible thing on this menu during a demo: they are the §6 queries that show the database being used for more than row lookups, and they render through ui.page() like every other table.
"""

from .. import ui
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


def report_top_bidders(session):
    buyer._not_built_yet("The top bidders report", 16)


def report_revenue_by_category(session):
    buyer._not_built_yet("The revenue by category report", 16)


def report_unpaid_wins(session):
    buyer._not_built_yet("The won-but-unpaid report", 16)


def report_active_auctions(session):
    buyer._not_built_yet("The active auctions report", 16)


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
