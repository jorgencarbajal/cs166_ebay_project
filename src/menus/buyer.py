"""The Buyer's menu: browse, search, bid, pay, track deliveries, edit your profile."""

from decimal import Decimal

from .. import auctions, bids, ui


def _not_built_yet(feature, issue):
    """Say plainly that a feature is not written yet, and which issue covers it."""
    ui.blank()
    ui.warn(f"{feature} is not built yet -- issue #{issue}.")


def browse_auctions(session):
    rows = auctions.browse(session)

    columns = [
        ("auction_id", "ID"),
        "item_name",
        "category",
        ("starting_price", "Starting"),
        ("current_highest_bid", "High Bid"),
        ("seller_login", "Seller"),
    ]

    ui.page(rows, columns, title="Open auctions")


def search_items(session):
    ui.blank()
    ui.info("Leave a field blank to skip it. Blank everything to list every open auction.")
    ui.blank()

    name = ui.prompt("Item name contains", required=False, max_length=100)
    category = ui.prompt("Category", required=False, max_length=50)

    min_price = None
    max_price = None

    if ui.confirm("Filter by starting price?", default=False):
        min_price = ui.prompt_decimal("Lowest starting price", minimum=Decimal("0.00"))
        max_price = ui.prompt_decimal("Highest starting price", minimum=min_price)

    include_closed = ui.confirm("Include closed auctions?", default=False)

    rows = auctions.search(
        session,
        name=name,
        category=category,
        min_price=min_price,
        max_price=max_price,
        include_closed=include_closed,
    )

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

    a = auctions.detail(session, auction_id)
    bid_rows = bids.history(session, auction_id)

    ui.blank()
    ui.heading(f"{a['item_name']}  (auction {a['auction_id']})")

    def field(label, value):
        ui.info(f"{(label + ':').ljust(16)}{value}")

    field("Category", a["category"])
    field("Condition", a["item_condition"] or "not stated")
    field("Seller", a["seller_login"])
    field("Status", a["auction_status"])
    field("Starting price", f"${a['starting_price']:,.2f}")

    if a["bid_count"] == 0:
        field("Highest bid", "no bids yet")
    else:
        field("Highest bid", f"${a['current_highest_bid']:,.2f}  ({a['bid_count']} bids)")

    if a["auction_status"] == "Closed":
        field("Winner", a["winner_login"] or "nobody bid")

    if a["description"]:
        ui.blank()
        ui.info(a["description"])

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
    auction_id = ui.prompt_int("Auction id", minimum=1)

    amount = ui.prompt_decimal("Your bid", minimum=Decimal("0.01"))

    bid = bids.place(session, auction_id, amount)

    ui.blank()
    ui.success(f"Bid #{bid['bid_id']} placed on auction {auction_id} for ${bid['bid_amount']:,.2f}.")
    ui.info("You are the highest bidder until someone outbids you.")


def my_bids(session):
    rows = bids.list_for_buyer(session)

    columns = [
        ("bid_id", "Bid"),
        ("auction_id", "Auction"),
        "item_name",
        ("bid_amount", "Your Bid"),
        ("current_highest_bid", "High Bid"),
        ("outcome", "Outcome"),
        ("bid_timestamp", "Placed"),
    ]

    ui.page(rows, columns, title="Your bids")


def pay_for_won_auction(session):
    _not_built_yet("Paying for a won auction", 11)


def track_deliveries(session):
    _not_built_yet("Tracking deliveries", 12)


def view_profile(session):
    _not_built_yet("Viewing your profile", 6)


def edit_profile(session):
    _not_built_yet("Editing your profile", 6)


TITLE = "Buyer menu"

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
