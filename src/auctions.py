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
from .errors import AuctionClosed, NotAuthorized, NotFound


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


def detail(session, auction_id):
    """
    Return everything known about one auction, as a single row.

    Read-only and unrestricted -- anyone logged in may look at any auction, open or closed, exactly as browse() lets anyone see the open ones. There is no require_role() and no ownership check.

    This is the one query in the project that is deliberately wide. Every other SELECT returns only the columns a table on screen needs, because a table with fifteen columns is unreadable in a terminal. A detail view is the opposite situation -- one record, printed down the screen as labelled lines, so the description and the condition are worth fetching here and nowhere else.

    The bid_count column is a scalar subquery: a SELECT nested inside the column list that returns exactly one value per outer row. It is used instead of a JOIN to bid with a GROUP BY, because joining would multiply the auction row by the number of bids and force everything else into an aggregate to collapse it again. A subquery counts without disturbing the shape of the result.

    Args:
        session (auth.Session): the logged-in user. Not used in the query -- every feature function takes one so the signature is uniform.
        auction_id (int): which auction.

    Returns:
        dict: one row, keyed by column name. winner_login is None unless the auction is Closed and somebody bid.

    Raises:
        NotFound: no auction has that id.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                a.auction_id,
                a.auction_status,
                a.current_highest_bid,
                a.seller_login,
                a.winner_login,
                i.item_id,
                i.item_name,
                i.category,
                i.starting_price,
                i.item_condition,
                i.description,
                (SELECT COUNT(*) FROM bid b WHERE b.auction_id = a.auction_id) AS bid_count
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            WHERE a.auction_id = %s
            """,
            (auction_id,),
        ).fetchone()

    # Unlike browse(), an empty result here is a real failure rather than a normal answer. Browse asks "what is open" and nothing being open is fine; this asks for one specific auction by id, so not finding it means the id was wrong.
    if row is None:
        raise NotFound("auction", auction_id)

    return row


def end(session, auction_id):
    """
    Close an auction and record whoever was winning it as the winner.

    The second transaction in the project, and it is deliberately built the same way as bids.place() -- lock the auction row first, check the rules against what the lock guarantees is current, then write. Read that function before this one; the reasoning behind the lock is written out there in full and is not repeated here.

    Auctions have no end time anywhere in the schema. The only timestamp in the whole database is bid.bid_timestamp, so nothing expires on its own and no clock closes anything. This function is the only way an auction ever stops being Active, which is why it is the counterpart to place() rather than a footnote to it.

    WHY THE LOCK IS NEEDED HERE TOO. Closing reads the highest bid and then writes a winner based on it. Without the lock, a bid could land in the gap between those two steps and the auction would close naming the wrong person -- the bidder would be told their bid succeeded while the winner column recorded somebody they had just outbid. The lock makes the pair atomic: a bid arriving mid-close waits, then finds the auction Closed and is correctly refused by place()'s own status check.

    Args:
        session (auth.Session): the logged-in user. Must be the auction's seller, or any Admin.
        auction_id (int): which auction to close.

    Returns:
        dict: auction_id, winner_login, and final_price. winner_login is None when nobody bid, and the menu is expected to say so rather than printing an empty name.

    Raises:
        NotFound: no auction has that id.
        AuctionClosed: it is already Closed. Closing twice would overwrite a recorded winner, so it is refused rather than silently ignored.
        NotAuthorized: the caller is neither the seller nor an Admin.
    """
    with get_connection() as conn:
        # No join this time, so a plain FOR UPDATE is enough -- there is only one table in the query and therefore only one row to lock. bids.place() needs FOR UPDATE OF a purely because its query also joins item.
        # This is the same auction row that place() locks, which is exactly the point: closing an auction and bidding on it are the two operations that must never interleave, and they serialize against each other because they contend for this one row.
        auction = conn.execute(
            """
            SELECT auction_id, seller_login, auction_status, current_highest_bid
            FROM auction
            WHERE auction_id = %s
            FOR UPDATE
            """,
            (auction_id,),
        ).fetchone()

        if auction is None:
            raise NotFound("auction", auction_id)

        # RULE 1 -- it must still be open. Closing an already-Closed auction would overwrite winner_login, quietly rewriting history for somebody who already won, so this is refused rather than treated as a harmless no-op.
        if auction["auction_status"] != "Active":
            raise AuctionClosed(auction_id)

        # RULE 2 -- the seller who owns it, or any Admin. Ownership is checked here rather than with require_role() because it is not a role question: most Sellers are not allowed to close this particular auction either. Admins are included because the spec gives them oversight of every auction, and because it makes the demo possible without logging out and back in.
        # NotAuthorized called with only an action and no role builds "You are not allowed to close this auction." -- the ownership wording rather than the role wording. See errors.py.
        if auction["seller_login"] != session.login and session.role != "Admin":
            raise NotAuthorized("close this auction")

        # Find whoever is winning. current_highest_bid already holds the amount, but not the person, and the winner_login column needs the person -- so the bid table is the only place this can come from.
        # ORDER BY bid_amount DESC takes the largest. The bid_timestamp ASC tiebreak means that if two bids somehow shared the top amount, the one placed first wins, which is the fair reading. In practice a tie cannot happen, because place() requires each bid to be strictly greater than the last -- the tiebreak is there so the query has one defined answer no matter what is in the table, including rows loaded straight from seed.sql.
        winner = conn.execute(
            """
            SELECT buyer_login, bid_amount
            FROM bid
            WHERE auction_id = %s
            ORDER BY bid_amount DESC, bid_timestamp ASC
            LIMIT 1
            """,
            (auction_id,),
        ).fetchone()

        # An auction nobody bid on closes with no winner, rather than refusing to close at all. A seller has to be able to withdraw a listing that drew no interest, and NULL is the schema's own way of saying "there isn't one" -- winner_login is nullable precisely so this state can be expressed.
        # winner_role must be set to NULL alongside it, not left alone. The column is CHECK (winner_role = 'Buyer') with a DEFAULT of 'Buyer', but column defaults only apply to INSERT -- an UPDATE that ignores the column leaves whatever was there before. Setting both to NULL together also satisfies the composite foreign key, which is skipped entirely when any of its columns is NULL.
        if winner is None:
            winner_login = None
            winner_role = None
            final_price = auction["current_highest_bid"]
        else:
            winner_login = winner["buyer_login"]
            # Spelled out rather than relying on the default, for the same reason bids.place() spells out buyer_role: it is the visible half of the schema's role-pinning trick and worth seeing at the point it is written.
            winner_role = "Buyer"
            # Taken from the bid row rather than from current_highest_bid. The two should be identical, and this is the one place worth preferring the bid table -- it is the real record, and current_highest_bid is only a copy of it.
            final_price = winner["bid_amount"]

        conn.execute(
            """
            UPDATE auction
            SET auction_status = 'Closed',
                winner_login = %s,
                winner_role = %s
            WHERE auction_id = %s
            """,
            (winner_login, winner_role, auction_id),
        )

    # Returned rather than printed, like everything else in this layer. winner_login of None is a real answer that the menu has to word differently, not a failure.
    return {
        "auction_id": auction_id,
        "winner_login": winner_login,
        "final_price": final_price,
    }
