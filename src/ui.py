"""
Everything the user sees.

The only module in the project that imports rich. It holds the shared console, the success/error/warn/info helpers, a table() that renders the dict_row dictionaries feature modules return, a numbered menu(), and prompt helpers that re-ask on bad input instead of crashing.

Money is NUMERIC(10,2) in the schema, so the prompts return Decimal and never float -- that conversion happens here once rather than being reinvented in six modules. Menu modules import this freely; feature modules must not import it at all.
"""

# Decimal is Python's exact decimal arithmetic. Money must never be float: 0.1 + 0.2 is 0.30000000000000004 in float, which is how you end up a cent off. InvalidOperation is what Decimal("abc") raises.
from decimal import Decimal, InvalidOperation
import sys

from rich import box
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm


# One Console for the whole program. rich uses it to detect terminal width and colour support, so sharing one keeps output consistent everywhere.
console = Console()


# The border style every table in the project uses. Changing this one name restyles all of them.
BOX = box.ROUNDED


# MESSAGES ---------------------------------------------------------------------------------------
#
# Four one-liners so the rest of the app never picks its own colours. Change the look here and the whole interface changes.
# The [green]...[/green] syntax is rich's markup, its own inline styling language.


def _terminal_handles(text):
    """
    Can this terminal display these characters?

    The server runs a UTF-8 session and shows the symbols properly. A Windows console is often cp1252, which cannot encode them at all -- it raises UnicodeEncodeError rather than printing something ugly. Since scripts/ui_demo.py is meant to run on a laptop too, we ask first and fall back rather than crashing.

    Asked in advance rather than by catching the failure, because rich buffers its output: an unencodable character blows up on some later print, not the one that queued it, so a try/except around the print does not catch it where you would expect.
    """
    try:
        # sys.stdout.encoding is the codec the terminal is using. Encoding the text against it is the direct test.
        text.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


# Decided once at import time, not per message, so the whole session looks consistent even if something odd happens to stdout later.
if _terminal_handles("✓✗⚠·"):
    # Each symbol is one column wide, so three trailing spaces line the text up at column 4.
    _OK, _BAD, _WARN, _INFO = "✓  ", "✗  ", "⚠  ", "·  "
else:
    # Two characters plus one space, also column 4, so messages align identically either way.
    _OK, _BAD, _WARN, _INFO = "OK ", "!! ", "?? ", "-- "


def success(message):
    console.print(f"[bold green]{_OK}[/bold green] {message}")


def error(message):
    console.print(f"[bold red]{_BAD}[/bold red] {message}")


def warn(message):
    console.print(f"[bold yellow]{_WARN}[/bold yellow] {message}")


def info(message):
    console.print(f"[dim]{_INFO}[/dim] {message}")


def blank():
    """A blank line. Exists so menu modules never have to call print() directly."""
    console.print()


def heading(text):
    """A titled rule across the terminal, for the top of a screen."""
    console.rule(f"[bold cyan]{text}[/bold cyan]")


# TABLES -----------------------------------------------------------------------------------------


def _header_for(key):
    """Turn a column key into a readable header: item_name -> Item Name."""
    return key.replace("_", " ").title()


def _normalize_columns(columns):
    """
    Accept either form of the columns argument and return a list of (key, header) pairs.

    Callers can pass plain keys and get automatic headers, or pass a pair to override one:
        ["item_name", "category"]                -> Item Name, Category
        [("item_name", "Item"), "category"]      -> Item, Category
    """
    pairs = []

    for column in columns:
        # isinstance(x, str) asks "is this a string?" -- a plain key. Anything else is assumed to be the (key, header) pair.
        if isinstance(column, str):
            pairs.append((column, _header_for(column)))
        else:
            pairs.append((column[0], column[1]))

    return pairs


def _format_cell(value):
    """Turn one database value into display text."""
    # A NULL column comes back as None. Printing "None" looks like a bug, so show a dim dash instead.
    if value is None:
        return "[dim]-[/dim]"

    # Every NUMERIC(10,2) column in this schema is money, so a Decimal gets a dollar sign and exactly two places. If a report query ever returns a non-money Decimal, cast it in SQL rather than complicating this.
    if isinstance(value, Decimal):
        return f"${value:,.2f}"

    # str() covers ints, timestamps, and text. Timestamps print as 2026-08-21 14:30:00, which is fine for a terminal.
    return str(value)


def table(rows, columns, title=None):
    """
    Render a list of dict_row dictionaries as a table.

    Args:
        rows: what a feature module returned -- a list of dicts keyed by column name.
        columns: which keys to show and in what order. See _normalize_columns for the accepted forms.
        title: optional caption above the table.
    """
    # An empty result is not an error, but silence would look broken, so say so plainly and stop.
    if not rows:
        info("Nothing to show.")
        return

    pairs = _normalize_columns(columns)

    grid = Table(title=title, box=BOX, header_style="bold cyan", title_style="bold")

    for _key, header in pairs:
        grid.add_column(header)

    for row in rows:
        # row.get(key) returns None instead of raising if a query did not select that column, and _format_cell turns None into a dash.
        grid.add_row(*[_format_cell(row.get(key)) for key, _header in pairs])

    console.print(grid)


def page(rows, columns, title=None, page_size=10):
    """
    Show a long result a screenful at a time.

    A terminal cannot display a thousand rows, and dumping them all just fills the scrollback. This walks through the list with [n]ext / [b]ack / [q]uit. Built once here and reused by browse, search, the admin user list, and the admin reports.
    """
    if not rows:
        info("Nothing to show.")
        return

    # Integer division that rounds up: 25 rows at 10 per page is 3 pages. Written as -(-a // b) because // rounds down.
    total_pages = -(-len(rows) // page_size)
    current = 0

    while True:
        start = current * page_size
        # Slicing past the end is safe in Python -- rows[20:30] on a 25-item list just gives the last 5.
        chunk = rows[start:start + page_size]

        caption = f"{title} " if title else ""
        table(chunk, columns, title=f"{caption}({start + 1}-{start + len(chunk)} of {len(rows)})")

        # One page means there is nothing to navigate, so do not make them press a key to leave.
        if total_pages == 1:
            return

        # Build the list of moves that are actually available, so "next" is not offered on the last page.
        choices = []
        if current < total_pages - 1:
            choices.append("n")
        if current > 0:
            choices.append("b")
        choices.append("q")

        # The backslashes matter: rich reads square brackets as its own styling markup, so a bare [n]ext prints as "ext". Escaping with \[ tells rich to show the bracket instead of eating it.
        labels = {"n": "\\[n]ext", "b": "\\[b]ack", "q": "\\[q]uit"}
        hint = " / ".join(labels[c] for c in choices)

        # show_choices and show_default are both off because the hint above already says what the options are -- otherwise rich appends its own "[n/b/q] (q)" on the end.
        answer = Prompt.ask(
            f"Page {current + 1} of {total_pages}  {hint}",
            choices=choices,
            default="q",
            show_choices=False,
            show_default=False,
        )

        if answer == "n":
            current += 1
        elif answer == "b":
            current -= 1
        else:
            return


# MENUS ------------------------------------------------------------------------------------------


def menu(title, options):
    """
    Print a numbered menu and return the key of whatever was chosen.

    Args:
        title: heading above the list.
        options: list of (key, label) pairs. A list rather than a dict because order is the whole point of a menu.

    Returns:
        The key of the chosen option -- a short string like "bid" or "quit" that the calling menu switches on. Returning the key rather than the number means renumbering a menu never breaks the dispatch code.
    """
    blank()
    heading(title)

    for number, (_key, label) in enumerate(options, start=1):
        # enumerate(options, start=1) walks the list handing back (1, first), (2, second) ... so we do not track a counter by hand.
        console.print(f"  [bold]{number}[/bold]. {label}")

    blank()

    # Build the acceptable answers as strings, since input always arrives as text.
    valid = [str(n) for n in range(1, len(options) + 1)]

    # rich rejects anything not in choices and re-asks by itself, so there is no loop to write here.
    answer = Prompt.ask("Choose", choices=valid, show_choices=False)

    # Answers are 1-based, list indexes are 0-based, hence the -1. The [0] takes the key out of the (key, label) pair.
    return options[int(answer) - 1][0]


# PROMPTS ----------------------------------------------------------------------------------------
#
# Every one of these re-asks on bad input rather than raising. A grader typing "abc" into a price field must not get a traceback.


def prompt(label, default=None, required=True, max_length=None):
    """
    Ask for a line of text.

    Args:
        default: shown in brackets and used when the user just presses Enter.
        required: when False an empty answer is allowed and returns "". That is what "leave this field unchanged" looks like on the profile and listing edit screens.
        max_length: the column width from the schema. login is VARCHAR(50) and address is VARCHAR(255), and catching it here gives a readable message instead of a database truncation error.
    """
    while True:
        answer = Prompt.ask(label, default=default) if default is not None else Prompt.ask(label)

        # Prompt.ask can hand back None when there is no default and nothing was typed, so normalise to a string before stripping whitespace.
        answer = (answer or "").strip()

        if not answer and required:
            error("This field cannot be empty.")
            continue

        if max_length and len(answer) > max_length:
            error(f"Too long -- {max_length} characters maximum, you typed {len(answer)}.")
            continue

        return answer


def prompt_password(label="Password"):
    """Ask for a password without echoing it to the screen."""
    while True:
        # password=True is rich's masked input -- the characters are not displayed as they are typed.
        answer = Prompt.ask(label, password=True)

        if not answer:
            error("Password cannot be empty.")
            continue

        return answer


def prompt_int(label, default=None, minimum=None, maximum=None):
    """Ask for a whole number, re-asking until one arrives."""
    while True:
        answer = prompt(label, default=str(default) if default is not None else None)

        try:
            value = int(answer)
        except ValueError:
            # int("abc") raises ValueError. Catch it, explain, ask again.
            error("Enter a whole number.")
            continue

        if minimum is not None and value < minimum:
            error(f"Must be at least {minimum}.")
            continue

        if maximum is not None and value > maximum:
            error(f"Must be no more than {maximum}.")
            continue

        return value


def prompt_decimal(label, default=None, minimum=None):
    """
    Ask for an amount of money and return it as a Decimal.

    This is the single place where typed text becomes money. Nothing else in the project should call Decimal() on user input.
    """
    while True:
        answer = prompt(label, default=str(default) if default is not None else None)

        # Let people type $45.50 or 1,200.00 without it counting as an error.
        answer = answer.replace("$", "").replace(",", "")

        try:
            value = Decimal(answer)
        except InvalidOperation:
            # InvalidOperation is Decimal's version of ValueError -- what Decimal("abc") raises.
            error("Enter an amount, for example 45.50")
            continue

        if minimum is not None and value < minimum:
            error(f"Must be at least ${minimum:,.2f}.")
            continue

        # quantize() forces exactly two decimal places to match NUMERIC(10,2), so 45.5 becomes 45.50 and 45.555 is rounded before it ever reaches the database.
        return value.quantize(Decimal("0.01"))


def confirm(label, default=False):
    """Ask a yes/no question. Returns True or False."""
    return Confirm.ask(label, default=default)
