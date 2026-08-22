"""
The auction table: browsing, searching, and closing.

The busiest module in the project. It backs browse (paginated listings joined to item), search (filters on name, category, price, and status), the detail view for a single auction, and ending an auction.

Ending is a transaction: find the highest bidder, write winner_login, set auction_status to Closed. Note that current_highest_bid lives on this table but is maintained by bids.py -- the two must stay in sync, which is why bid placement locks the auction row. Auctions have no end time anywhere in the schema; they close only when their seller closes them. Used by every menu.

THIS IS THE REFERENCE SLICE. browse() below is the first feature written, so it is the pattern every other feature copies. Four things it does that yours should too:

    1. Takes a Session, never a bare login. Identity comes from session.login, so a caller cannot act as someone else.
    2. Opens its own connection with `with get_connection() as conn:`. The menu does not open one and pass it in.
    3. Returns data. It does not print, does not import ui, and does not know a terminal exists.
    4. Writes its SQL inline as a parameterized string, with values passed as psycopg's second argument -- never built with an f-string.
"""

from .db import get_connection


def browse(session):
    """
    Return every Active auction, newest first.

    Available to every logged-in user (spec section 6.1), so there is no require_role() call here -- Buyers, Sellers, and Admins all browse the same list.

    Only Active auctions come back. Browse answers "what can I bid on", and a closed auction cannot be bid on. Closed ones are still reachable through search, which has a status filter, and through the auction detail screen.

    No LIMIT or OFFSET. The whole result is returned and ui.page() in the menu layer does the paging. That means one query instead of one per page, no offset bookkeeping, and pagination that behaves identically in browse, search, and the admin reports because it is literally the same function. If the dataset in issue #17 ever makes this slow, this is the place to add LIMIT -- not the menu.

    Args:
        session (auth.Session): the logged-in user. Not used in the query, but every feature function takes one so the signature is uniform and permission checks can be added later without changing callers.

    Returns:
        list[dict]: one dict per auction, keyed by column name. Empty list if nothing is Active.
    """
    with get_connection() as conn:
        # The JOIN is the whole point of this query: auction holds the price and status, item holds the name and category, and the screen needs both. Joining on item_id is safe and cannot duplicate rows -- auction.item_id is UNIQUE and NOT NULL, so each auction matches exactly one item.
        rows = conn.execute(
            """
            SELECT
                a.auction_id,
                i.item_name,
                i.category,
                i.starting_price,
                a.current_highest_bid,
                a.seller_login
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            WHERE a.auction_status = 'Active'
            ORDER BY a.auction_id DESC
            """
        ).fetchall()

    # fetchall() returns a list of dicts because db.py sets dict_row as the row factory, so the menu reads row["item_name"] rather than row[1]. An empty list is a normal answer, not an error -- ui.page() prints "Nothing to show." for it.
    return rows
