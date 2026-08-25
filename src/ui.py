"""Everything the user sees."""

from decimal import Decimal, InvalidOperation
import sys

from rich import box
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm


console = Console()


BOX = box.ROUNDED


def _terminal_handles(text):
    """Can this terminal display these characters?"""
    try:
        text.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


if _terminal_handles("✓✗⚠·"):
    _OK, _BAD, _WARN, _INFO = "✓  ", "✗  ", "⚠  ", "·  "
else:
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
    """A blank line."""
    console.print()


def heading(text):
    """A titled rule across the terminal, for the top of a screen."""
    console.rule(f"[bold cyan]{text}[/bold cyan]")


def _header_for(key):
    """Turn a column key into a readable header: item_name -> Item Name."""
    return key.replace("_", " ").title()


def _normalize_columns(columns):
    """Accept either form of the columns argument and return a list of (key, header) pairs."""
    pairs = []

    for column in columns:
        if isinstance(column, str):
            pairs.append((column, _header_for(column)))
        else:
            pairs.append((column[0], column[1]))

    return pairs


def _format_cell(value):
    """Turn one database value into display text."""
    if value is None:
        return "[dim]-[/dim]"

    if isinstance(value, Decimal):
        return f"${value:,.2f}"

    return str(value)


def table(rows, columns, title=None):
    """Render a list of dict_row dictionaries as a table."""
    if not rows:
        info("Nothing to show.")
        return

    pairs = _normalize_columns(columns)

    grid = Table(title=title, box=BOX, header_style="bold cyan", title_style="bold")

    for _key, header in pairs:
        grid.add_column(header)

    for row in rows:
        grid.add_row(*[_format_cell(row.get(key)) for key, _header in pairs])

    console.print(grid)


def page(rows, columns, title=None, page_size=10):
    """Show a long result a screenful at a time."""
    if not rows:
        info("Nothing to show.")
        return

    total_pages = -(-len(rows) // page_size)
    current = 0

    while True:
        start = current * page_size
        chunk = rows[start:start + page_size]

        caption = f"{title} " if title else ""
        table(chunk, columns, title=f"{caption}({start + 1}-{start + len(chunk)} of {len(rows)})")


        choices = []
        if current < total_pages - 1:
            choices.append("n")
        if current > 0:
            choices.append("b")
        choices.append("q")

        labels = {"n": "\\[n]ext", "b": "\\[b]ack", "q": "\\[q]uit"}
        hint = " / ".join(labels[c] for c in choices)

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


def menu(title, options):
    """
    Print a numbered menu and return the key of whatever was chosen.
    Returns the key of the chosen option -- a short string like "bid" or "quit" that the calling menu.
    """
    blank()
    heading(title)

    for number, (_key, label) in enumerate(options, start=1):
        console.print(f"  [bold]{number}[/bold]. {label}")

    blank()

    valid = [str(n) for n in range(1, len(options) + 1)]

    answer = Prompt.ask("Choose", choices=valid, show_choices=False)

    return options[int(answer) - 1][0]


def prompt(label, default=None, required=True, max_length=None):
    """Ask for a line of text."""
    while True:
        answer = Prompt.ask(label, default=default) if default is not None else Prompt.ask(label)

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
    """Ask for an amount of money and return it as a Decimal."""
    while True:
        answer = prompt(label, default=str(default) if default is not None else None)

        answer = answer.replace("$", "").replace(",", "")

        try:
            value = Decimal(answer)
        except InvalidOperation:
            error("Enter an amount, for example 45.50")
            continue

        if minimum is not None and value < minimum:
            error(f"Must be at least ${minimum:,.2f}.")
            continue

        return value.quantize(Decimal("0.01"))


def confirm(label, default=False):
    """Ask a yes/no question."""
    return Confirm.ask(label, default=default)
