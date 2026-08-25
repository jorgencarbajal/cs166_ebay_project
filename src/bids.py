"""The bid table: placing bids and reading bid history."""

from .auth import require_role
from .db import get_connection
from .errors import AuctionClosed, BidTooLow, NotFound, SelfBid


def place(session, auction_id, amount):
    """
    Place a bid on an auction, or raise explaining why it is not allowed.
    Returns dict: the row that was just written, with keys bid_id, bid_amount and bid_timestamp.
    """
    require_role(session, "Buyer", "place a bid")

    with get_connection() as conn:
        auction = conn.execute(
            """
            SELECT
                a.auction_id,
                a.seller_login,
                a.auction_status,
                a.current_highest_bid,
                i.starting_price
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            WHERE a.auction_id = %s
            FOR UPDATE OF a
            """,
            (auction_id,),
        ).fetchone()

        if auction is None:
            raise NotFound("auction", auction_id)

        if auction["auction_status"] != "Active":
            raise AuctionClosed(auction_id)

        if auction["seller_login"] == session.login:
            raise SelfBid()

        minimum = max(auction["current_highest_bid"], auction["starting_price"])

        if amount <= minimum:
            raise BidTooLow(amount, minimum)

        bid = conn.execute(
            """
            INSERT INTO bid (auction_id, buyer_login, buyer_role, bid_amount)
            VALUES (%s, %s, 'Buyer', %s)
            RETURNING bid_id, bid_amount, bid_timestamp
            """,
            (auction_id, session.login, amount),
        ).fetchone()

        conn.execute(
            """
            UPDATE auction
            SET current_highest_bid = %s
            WHERE auction_id = %s
            """,
            (amount, auction_id),
        )

    return bid


def history(session, auction_id):
    """
    Return every bid placed on one auction, highest first.
    Returns list[dict]: bid_id, buyer_login, bid_amount, bid_timestamp.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                bid_id,
                buyer_login,
                bid_amount,
                bid_timestamp
            FROM bid
            WHERE auction_id = %s
            ORDER BY bid_amount DESC
            """,
            (auction_id,),
        ).fetchall()

    return rows


def list_for_buyer(session):
    """
    Return every bid this user has placed, newest first, each labelled with how it turned out.
    Returns list[dict]: keyed by column name, with an extra "outcome" key holding the label.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                b.bid_id,
                b.auction_id,
                i.item_name,
                b.bid_amount,
                a.current_highest_bid,
                a.auction_status,
                b.bid_timestamp,
                CASE
                    WHEN a.auction_status = 'Closed' AND a.winner_login = b.buyer_login THEN 'Won'
                    WHEN a.auction_status = 'Closed' THEN 'Lost'
                    WHEN b.bid_amount = a.current_highest_bid THEN 'Leading'
                    ELSE 'Outbid'
                END AS outcome
            FROM bid b
            JOIN auction a ON a.auction_id = b.auction_id
            JOIN item i ON i.item_id = a.item_id
            WHERE b.buyer_login = %s
            ORDER BY b.bid_timestamp DESC
            """,
            (session.login,),
        ).fetchall()

    return rows
