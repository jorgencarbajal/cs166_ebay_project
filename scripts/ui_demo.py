"""
Look at the interface without needing a database.

src/ui.py imports nothing but rich and decimal -- no db, no psycopg, no .env -- so the entire look of the application can be judged on any machine, including your laptop. That is what this script is for.

    .venv/Scripts/python.exe scripts/ui_demo.py            # pick sections from a menu (Windows)
    .venv/bin/python scripts/ui_demo.py                    # same, on the server
    .venv/bin/python scripts/ui_demo.py --all              # every section in order
    .venv/bin/python scripts/ui_demo.py --static           # only the sections that need no typing

Three jobs. Deciding the house style before three people write menus against it, showing a new teammate what the helpers look like, and producing the screenshots §19 of the spec wants in the report.

All data below is invented and lives in this file. Nothing here touches the database.
"""

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import ui

# The one place outside src/ui.py allowed to import rich directly. The whole point of the tables section is comparing box styles so we can pick one and put it in ui.py, which cannot be done through ui.table().
from rich import box
from rich.table import Table


# FAKE DATA --------------------------------------------------------------------------------------
#
# Shaped exactly like what psycopg's dict_row hands back, so the demo exercises the real code path.

NAMES = [
    "Vintage Leather Jacket", "Mechanical Keyboard", "First Edition Dune",
    "Acoustic Guitar", "Film Camera", "Wool Rug", "Chess Set",
    "Espresso Machine", "Mountain Bike", "Desk Lamp", "Record Player",
    "Wristwatch", "Telescope", "Cast Iron Skillet", "Fountain Pen",
    "Vinyl Box Set", "Drafting Table", "Hiking Boots", "Ceramic Vase",
    "Noise Cancelling Headphones", "Antique Mirror", "Sewing Machine",
    "Rowing Machine", "Tool Chest", "Globe",
]

CATEGORIES = ["Clothing", "Electronics", "Books", "Music", "Home", "Sports"]

AUCTIONS = [
    {
        "auction_id": i,
        "item_name": NAMES[i - 1],
        "category": CATEGORIES[i % len(CATEGORIES)],
        "starting_price": Decimal("15.00") + Decimal(i) * Decimal("12.50"),
        # Every fourth auction has no bids yet, so the dim dash for NULL shows up in the output.
        "current_highest_bid": None if i % 4 == 0 else Decimal("15.00") + Decimal(i) * Decimal("31.75"),
        "seller_login": f"seller{(i % 5) + 1}",
        "auction_status": "Closed" if i % 3 == 0 else "Active",
    }
    for i in range(1, len(NAMES) + 1)
]

AUCTION_COLUMNS = [
    ("auction_id", "ID"),
    ("item_name", "Item"),
    "category",
    ("starting_price", "Start"),
    ("current_highest_bid", "High Bid"),
    ("auction_status", "Status"),
]

BIDS = [
    {"bid_id": 104, "buyer_login": "buyer3", "bid_amount": Decimal("242.00"), "bid_timestamp": datetime(2026, 8, 21, 14, 31)},
    {"bid_id": 103, "buyer_login": "buyer1", "bid_amount": Decimal("230.50"), "bid_timestamp": datetime(2026, 8, 21, 13, 5)},
    {"bid_id": 102, "buyer_login": "buyer7", "bid_amount": Decimal("199.99"), "bid_timestamp": datetime(2026, 8, 20, 22, 47)},
    {"bid_id": 101, "buyer_login": "buyer3", "bid_amount": Decimal("150.00"), "bid_timestamp": datetime(2026, 8, 20, 9, 12)},
]

BID_COLUMNS = [("bid_id", "Bid"), ("buyer_login", "Bidder"), ("bid_amount", "Amount"), ("bid_timestamp", "Placed")]


# SECTIONS ---------------------------------------------------------------------------------------


def _can_encode(text):
    """
    Can this terminal actually display these characters?

    Asked in advance rather than by catching the failure, because rich buffers its output -- a character it cannot encode blows up on some later print, not the one that queued it, so a try/except around the print does not catch it where you would expect.
    """
    try:
        # sys.stdout.encoding is the codec the terminal is using: 'utf-8' on the server, often 'cp1252' on Windows. Encoding the text against it is the direct test.
        text.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def demo_messages():
    """The four status helpers, plus the ASCII-versus-symbols decision."""
    ui.blank()
    ui.heading("Messages")

    ui.info("These four are the only way anything gets said to the user.")
    ui.blank()

    ui.success("Bid placed. Your bid id is 105.")
    ui.error("Your bid of $10.00 must be greater than $242.00.")
    ui.warn("This auction has no bids. Closing it now leaves no winner.")
    ui.info("Showing 10 of 25 auctions.")

    ui.blank()
    ui.info("Current prefixes are plain ASCII, chosen so they cannot break. The alternative is symbols, which look better wherever they work -- but they do not work everywhere.")
    ui.blank()

    # Printed straight through the console rather than through ui.success, because the point is to compare against what ui.success currently does.
    ui.console.print("[bold green]OK[/bold green]  Bid placed. Your bid id is 105.")
    ui.console.print("[bold red]!![/bold red]  Your bid of $10.00 must be greater.")
    ui.console.print("[bold yellow]??[/bold yellow]  This auction has no bids.")
    ui.blank()

    if _can_encode("✓✗⚠"):
        ui.console.print("[bold green]✓[/bold green]   Bid placed. Your bid id is 105.")
        ui.console.print("[bold red]✗[/bold red]   Your bid of $10.00 must be greater.")
        ui.console.print("[bold yellow]⚠[/bold yellow]   This auction has no bids.")
        ui.blank()
        ui.success("This terminal renders the symbols. If the server does too, they are worth switching to.")
    else:
        ui.warn(f"This terminal cannot encode the symbols -- its output encoding is {sys.stdout.encoding!r}, which has no room for them.")
        ui.info("That is exactly why ui.py ships with ASCII. Run this on the server before deciding; a proper UTF-8 SSH session normally handles them fine.")


def _render_with_box(box_style, label):
    """Build the auctions table by hand with one specific border style, for comparison."""
    grid = Table(title=f"{label}", box=box_style, header_style="bold cyan", title_style="bold")

    for column in AUCTION_COLUMNS:
        grid.add_column(column[1] if isinstance(column, tuple) else column.replace("_", " ").title())

    for row in AUCTIONS[:4]:
        grid.add_row(
            str(row["auction_id"]),
            row["item_name"],
            row["category"],
            f"${row['starting_price']:,.2f}",
            "[dim]-[/dim]" if row["current_highest_bid"] is None else f"${row['current_highest_bid']:,.2f}",
            row["auction_status"],
        )

    ui.console.print(grid)
    ui.blank()


def demo_tables():
    """ui.table() as it stands, then the same rows in every border style worth considering."""
    ui.blank()
    ui.heading("Tables")

    ui.info("ui.table() takes the dicts a feature module returns and the list of columns to show. Decimals become money, NULLs become a dim dash, headers come from the column names.")
    ui.blank()

    ui.table(AUCTIONS[:6], AUCTION_COLUMNS, title="Active auctions")

    ui.blank()
    ui.info("An empty result is not silence:")
    ui.table([], AUCTION_COLUMNS)

    ui.blank()
    ui.info("A narrower table -- the bid history from the auction detail screen:")
    ui.table(BIDS, BID_COLUMNS, title="Bid history for auction 8")

    ui.blank()
    ui.heading("Border styles to choose from")
    ui.info("Same four rows, six different borders. Pick one and it becomes the look of every table in the project.")
    ui.blank()

    _render_with_box(box.HEAVY_HEAD, "HEAVY_HEAD  (what ui.py uses now)")
    _render_with_box(box.ROUNDED, "ROUNDED")
    _render_with_box(box.SIMPLE, "SIMPLE")
    _render_with_box(box.SIMPLE_HEAD, "SIMPLE_HEAD")
    _render_with_box(box.MINIMAL, "MINIMAL")
    _render_with_box(box.ASCII, "ASCII  (safest over a bad SSH connection)")


def demo_paging():
    """The paging helper, on enough rows to actually page."""
    ui.blank()
    ui.heading("Paging")

    ui.info("25 auctions, 10 to a page. Navigation adapts -- no [n]ext on the last page, no [b]ack on the first. Press n, b, and q to get a feel for it.")
    ui.info("Worth judging: is 10 rows right for the height of your terminal?")

    ui.page(AUCTIONS, AUCTION_COLUMNS, title="All auctions", page_size=10)


def demo_menus():
    """The numbered menu, at the three sizes the real application will use."""
    ui.blank()
    ui.heading("Menus")

    ui.info("menu() returns the key of the choice, not its number, so renumbering a menu never breaks the code behind it.")

    choice = ui.menu("Buyer menu", [
        ("browse", "Browse items"),
        ("search", "Search auctions"),
        ("detail", "View an auction"),
        ("bid", "Place a bid"),
        ("payments", "My payments"),
        ("profile", "My profile"),
        ("logout", "Log out"),
    ])

    ui.success(f"menu() returned {choice!r} -- that string is what the calling code switches on.")

    ui.blank()
    ui.info("A short one, the kind the opening screen uses:")

    choice = ui.menu("Welcome", [("login", "Log in"), ("register", "Register"), ("quit", "Quit")])
    ui.success(f"menu() returned {choice!r}")


def demo_prompts():
    """Every prompt, deliberately including the ways they refuse bad input."""
    ui.blank()
    ui.heading("Prompts")

    ui.info("All of these re-ask instead of crashing. Try to break them -- empty answers, letters where a number belongs, a very long username.")
    ui.blank()

    login = ui.prompt("Username", max_length=50)
    ui.success(f"got {login!r}")

    password = ui.prompt_password()
    ui.success(f"got {len(password)} characters, not echoed to the screen")

    ui.blank()
    ui.info("Blank is allowed when a field is optional -- this is how 'leave unchanged' works on the edit screens:")
    category = ui.prompt("Favorite category (blank to skip)", required=False)
    ui.success(f"got {category!r}")

    ui.blank()
    ui.info("Money comes back as Decimal, never float. Dollar signs and commas are accepted, and the result is forced to two places:")
    amount = ui.prompt_decimal("Bid amount", minimum=Decimal("0.01"))
    ui.success(f"got {amount!r}  -- type is {type(amount).__name__}")

    ui.blank()
    quantity = ui.prompt_int("Pick a number between 1 and 10", minimum=1, maximum=10)
    ui.success(f"got {quantity!r}")

    ui.blank()
    if ui.confirm("Was that acceptable?", default=True):
        ui.success("Good.")
    else:
        ui.warn("Noted -- say what you would rather have.")


def demo_walkthrough():
    """One realistic screen sequence, to judge how the pieces read together rather than one at a time."""
    ui.blank()
    ui.heading("A real screen sequence")

    ui.info("Browsing, then opening one auction, then bidding on it. This is what a menu module will actually produce.")

    ui.blank()
    ui.table(AUCTIONS[:5], AUCTION_COLUMNS, title="Auctions")

    auction_id = ui.prompt_int("Auction to view", default=8)

    row = AUCTIONS[7]

    ui.blank()
    ui.heading(f"Auction {auction_id} -- {row['item_name']}")
    ui.console.print(f"  Category      {row['category']}")
    ui.console.print(f"  Seller        {row['seller_login']}")
    ui.console.print(f"  Start price   ${row['starting_price']:,.2f}")
    ui.console.print(f"  Current bid   [bold]${BIDS[0]['bid_amount']:,.2f}[/bold]  by {BIDS[0]['buyer_login']}")
    ui.console.print(f"  Status        {row['auction_status']}")
    ui.blank()

    ui.table(BIDS, BID_COLUMNS, title="Bid history")

    ui.blank()
    ui.info(f"Your bid must be greater than ${BIDS[0]['bid_amount']:,.2f}.")

    amount = ui.prompt_decimal("Your bid", minimum=Decimal("0.01"))

    # The real bids.place() would raise BidTooLow here and the menu would print it. Faked so the demo needs no database.
    if amount <= BIDS[0]["bid_amount"]:
        ui.error(f"Your bid of ${amount:,.2f} must be greater than ${BIDS[0]['bid_amount']:,.2f}.")
        ui.info("That sentence came from errors.BidTooLow. The menu printed it and returned here.")
    else:
        ui.success(f"Bid placed. Your bid id is 105. You are now the highest bidder at ${amount:,.2f}.")


# DRIVER -----------------------------------------------------------------------------------------


# Sections that print and stop. Safe to run with no keyboard, which is what --static uses.
STATIC_SECTIONS = [
    ("messages", "Messages", demo_messages),
    ("tables", "Tables and border styles", demo_tables),
]

# Sections that ask questions and wait.
INTERACTIVE_SECTIONS = [
    ("paging", "Paging through a long result", demo_paging),
    ("menus", "Menus", demo_menus),
    ("prompts", "Prompts and how they reject bad input", demo_prompts),
    ("walkthrough", "A real screen sequence, end to end", demo_walkthrough),
]

ALL_SECTIONS = STATIC_SECTIONS + INTERACTIVE_SECTIONS


def run(sections):
    for _key, _label, function in sections:
        function()
        ui.blank()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview the terminal interface without a database.")
    parser.add_argument("--all", action="store_true", help="run every section in order")
    parser.add_argument("--static", action="store_true", help="run only the sections that need no typing")
    args = parser.parse_args(argv)

    if args.static:
        run(STATIC_SECTIONS)
        return 0

    if args.all:
        run(ALL_SECTIONS)
        return 0

    # No flags: let the reader pick sections one at a time, which also demonstrates menu() doing its actual job.
    while True:
        options = [(key, label) for key, label, _function in ALL_SECTIONS] + [("quit", "Quit")]
        choice = ui.menu("UI demo", options)

        if choice == "quit":
            ui.blank()
            ui.info("Nothing here touched the database.")
            return 0

        for key, _label, function in ALL_SECTIONS:
            if key == choice:
                function()
                break


# Entry point, not a test. Everything below runs only when the file is executed directly.
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        ui.blank()
        ui.info("Stopped.")
        sys.exit(1)
