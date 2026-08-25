"""The auction table: browsing, searching, and closing."""

from .db import get_connection
from .errors import AuctionClosed, NotAuthorized, NotFound


def browse(session):
    """
    Return every Active auction, newest first.
    Returns list[dict]: one dict per auction, keyed by column name.
    """
    with get_connection() as conn:
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

    return rows


def search(session, name=None, category=None, min_price=None, max_price=None, include_closed=False):
    """
    Return auctions matching whichever filters were actually supplied.
    Returns list[dict]: the same column shape browse() returns, plus auction_status.
    """
    conditions = []
    params = []

    if not include_closed:
        conditions.append("a.auction_status = 'Active'")

    if name:
        conditions.append("i.item_name ILIKE %s")
        params.append(f"%{name}%")

    if category:
        conditions.append("i.category ILIKE %s")
        params.append(category)

    if min_price is not None:
        conditions.append("i.starting_price >= %s")
        params.append(min_price)

    if max_price is not None:
        conditions.append("i.starting_price <= %s")
        params.append(max_price)

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                a.auction_id,
                i.item_name,
                i.category,
                i.starting_price,
                a.current_highest_bid,
                a.auction_status,
                a.seller_login
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            WHERE {where}
            ORDER BY a.auction_id DESC
            """,
            params,
        ).fetchall()

    return rows


def detail(session, auction_id):
    """
    Return everything known about one auction, as a single row.
    Returns dict: one row, keyed by column name. winner_login is None unless the auction is Closed and.
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

    if row is None:
        raise NotFound("auction", auction_id)

    return row


def end(session, auction_id):
    """
    Close an auction and record whoever was winning it as the winner.
    Returns dict: auction_id, winner_login, and final_price. winner_login is None when nobody bid.
    """
    with get_connection() as conn:
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

        if auction["auction_status"] != "Active":
            raise AuctionClosed(auction_id)

        if auction["seller_login"] != session.login and session.role != "Admin":
            raise NotAuthorized("close this auction")

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

        if winner is None:
            winner_login = None
            winner_role = None
            final_price = auction["current_highest_bid"]
        else:
            winner_login = winner["buyer_login"]
            winner_role = "Buyer"
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

    return {
        "auction_id": auction_id,
        "winner_login": winner_login,
        "final_price": final_price,
    }
