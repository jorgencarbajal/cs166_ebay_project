"""
The Buyer's menu: browse, search, bid, pay, track deliveries, edit your profile.

Every Buyer action lives here. Sellers and Admins get all of it too -- seller.py and admin.py start their own lists from this one -- because the spec makes browsing and bidding available to every user, with the role privileges layered on top.

Two names are exported and nothing else. TITLE is the heading, ACTIONS is a list of (key, label, function) triples, and menus/__init__.py does the rest: it draws the menu, calls whichever function was chosen, catches AppError, and loops. There is no while loop in this file and there should never be one.

An action function takes the Session and returns nothing. It calls into the feature modules (auctions.py, bids.py, payments.py), which return data or raise, and it prints the result through ui. That split is the whole architecture: the feature modules never print, and this file never contains business logic or SQL.

Adding an action is two steps. Write the function, then add a triple to ACTIONS.
"""

from decimal import Decimal

from .. import auctions, bids, ui


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
    ui.blank()
    ui.info("Leave a field blank to skip it. Blank everything to list every open auction.")
    ui.blank()

    # required=False is what makes a field skippable -- ui.prompt() returns "" instead of re-asking, and auctions.search() treats "" the same as None.
    # max_length matches the schema so a 300-character search string is refused here with a readable message rather than being sent to the database. item_name is VARCHAR(100) and category is VARCHAR(50).
    name = ui.prompt("Item name contains", required=False, max_length=100)
    category = ui.prompt("Category", required=False, max_length=50)

    # Money needs a different approach to the text fields above. ui.prompt_decimal() has no required=False, deliberately -- it is the one place text becomes money and letting it return "" would push that conversion out into every caller. So the price filter is opted into with a yes/no question instead, and both bounds are asked for only if the answer is yes.
    min_price = None
    max_price = None

    if ui.confirm("Filter by starting price?", default=False):
        min_price = ui.prompt_decimal("Lowest starting price", minimum=Decimal("0.00"))
        # The lower bound becomes the floor for the upper one, so "between $100 and $50" cannot be entered at all. Catching it in the prompt is better than accepting it and returning an empty result the user has to work out the reason for.
        max_price = ui.prompt_decimal("Highest starting price", minimum=min_price)

    # Closed auctions are excluded by default, matching browse(). This is the only way to find one, which matters for showing a completed sale during the demo.
    include_closed = ui.confirm("Include closed auctions?", default=False)

    rows = auctions.search(
        session,
        name=name,
        category=category,
        min_price=min_price,
        max_price=max_price,
        include_closed=include_closed,
    )

    # One extra column over browse_auctions() -- status, which is only interesting once closed auctions can appear in the results.
    columns = [
        ("auction_id", "ID"),
        "item_name",
        "category",
        ("starting_price", "Starting"),
        ("current_highest_bid", "High Bid"),
        ("auction_status", "Status"),
        ("seller_login", "Seller"),
    ]

    ui.page(rows, columns, title=f"Search results ({len(rows)} found)")


def view_auction(session):
    auction_id = ui.prompt_int("Auction id", minimum=1)

    # detail() raises NotFound on a bad id, so nothing below runs for one. That is also why it is called before history() -- it is the call that validates the id for both.
    a = auctions.detail(session, auction_id)
    bid_rows = bids.history(session, auction_id)

    ui.blank()
    ui.heading(f"{a['item_name']}  (auction {a['auction_id']})")

    # One record printed down the screen as labelled lines rather than across it as a table. A table needs its columns to line up across many rows, which is exactly wrong for a single row with twelve fields -- it would run off the side of any terminal.
    # ljust() pads each label out to the same width so the values form a straight column. The width is one wider than the longest label below, which leaves a single space of gap.
    def field(label, value):
        ui.info(f"{(label + ':').ljust(16)}{value}")

    field("Category", a["category"])
    field("Condition", a["item_condition"] or "not stated")
    field("Seller", a["seller_login"])
    field("Status", a["auction_status"])
    field("Starting price", f"${a['starting_price']:,.2f}")

    # A fresh auction shows current_highest_bid as 0.00, which on screen reads as "somebody bid nothing" rather than "nobody bid". Saying so in words is clearer, and it is the same distinction that trips people up in bids.place() -- 0.00 is the column default, not a real bid.
    if a["bid_count"] == 0:
        field("Highest bid", "no bids yet")
    else:
        field("Highest bid", f"${a['current_highest_bid']:,.2f}  ({a['bid_count']} bids)")

    # Only meaningful once the auction is Closed, and only then if somebody actually bid -- auctions.end() records NULL for an auction nobody wanted.
    if a["auction_status"] == "Closed":
        field("Winner", a["winner_login"] or "nobody bid")

    # description is TEXT and can be long, so it goes last and on its own line rather than in the aligned block, where a long value would wrap under the labels and break the column.
    if a["description"]:
        ui.blank()
        ui.info(a["description"])

    # page() rather than table() so a heavily bid auction pages instead of scrolling away. An empty list prints "Nothing to show." which is the right answer for an auction nobody has bid on.
    ui.blank()
    ui.page(
        bid_rows,
        [
            ("bid_id", "Bid"),
            ("buyer_login", "Bidder"),
            ("bid_amount", "Amount"),
            ("bid_timestamp", "Placed"),
        ],
        title="Bid history",
    )


def place_bid(session):
    # Ask which auction first. minimum=1 rejects 0 and negative ids in ui.prompt_int() before a pointless query goes out, and prompt_int() re-asks on its own if someone types letters, so nothing here has to handle bad input.
    auction_id = ui.prompt_int("Auction id", minimum=1)

    # Then the money. prompt_decimal() strips a leading $ or any commas, rounds to two places to match NUMERIC(10,2), and hands back a Decimal -- so bids.place() never sees a float and never sees a string.
    # minimum is one cent rather than zero because the schema has CHECK (bid_amount > 0) and a $0.00 bid would come back as a raw psycopg error instead of a sentence. This is only a floor on the number itself; whether it actually beats the auction is bids.place()'s job, since only it knows the starting price and the current high bid.
    amount = ui.prompt_decimal("Your bid", minimum=Decimal("0.01"))

    # The whole feature in one line. Every rule -- closed auction, bidding on your own listing, an amount that does not clear both floors -- raises from in there, and run_role_menu() catches it and prints it in red. That is why there is no try/except in this function.
    bid = bids.place(session, auction_id, amount)

    # Only reached if the bid was actually written. bid_id and bid_timestamp came back from the INSERT's RETURNING clause, so these are the database's real values rather than anything guessed on this side.
    ui.blank()
    ui.success(f"Bid #{bid['bid_id']} placed on auction {auction_id} for ${bid['bid_amount']:,.2f}.")
    ui.info("You are the highest bidder until someone outbids you.")


def my_bids(session):
    # Same three-line shape as browse_auctions() above: ask the feature module, hand the result to ui, say nothing about SQL.
    rows = bids.list_for_buyer(session)

    # bid_amount and current_highest_bid sit next to each other on purpose -- seeing "you bid $50, the auction is at $62" side by side explains the Outcome column without anyone having to ask.
    columns = [
        ("bid_id", "Bid"),
        ("auction_id", "Auction"),
        "item_name",
        ("bid_amount", "Your Bid"),
        ("current_highest_bid", "High Bid"),
        ("outcome", "Outcome"),
        ("bid_timestamp", "Placed"),
    ]

    # An empty list is the normal answer for someone who has never bid, and page() prints "Nothing to show." for it rather than an empty table.
    ui.page(rows, columns, title="Your bids")


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
