"""The four admin reports: aggregate queries that span the whole database."""

from .auth import require_role
from .db import get_connection


def top_bidders(session):
    """
    Every Buyer, with how much bidding they have actually done, busiest first.
    Returns list[dict]: one row per Buyer. highest_bid is None for a Buyer who has never bid.
    """
    require_role(session, "Admin", "view the reports")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.login,
                u.favorite_category,
                COUNT(b.bid_id) AS bids_placed,
                COUNT(DISTINCT b.auction_id) AS auctions_bid_on,
                MAX(b.bid_amount) AS highest_bid,
                (SELECT COUNT(*) FROM auction a WHERE a.winner_login = u.login) AS auctions_won
            FROM users u
            LEFT JOIN bid b ON b.buyer_login = u.login
            WHERE u.role = 'Buyer'
            GROUP BY u.login, u.favorite_category
            ORDER BY bids_placed DESC, highest_bid DESC NULLS LAST
            """
        ).fetchall()

    return rows


def revenue_by_category(session):
    """
    What each category of item actually sold for, best earner first.
    Returns list[dict]: one row per category that has sold at least one item.
    """
    require_role(session, "Admin", "view the reports")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                i.category,
                COUNT(*) AS items_sold,
                SUM(a.current_highest_bid) AS revenue,
                ROUND(AVG(a.current_highest_bid), 2) AS average_sale,
                MAX(a.current_highest_bid) AS largest_sale
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            WHERE a.auction_status = 'Closed'
              AND a.winner_login IS NOT NULL
            GROUP BY i.category
            HAVING SUM(a.current_highest_bid) > 0
            ORDER BY revenue DESC
            """
        ).fetchall()

    return rows


def unpaid_wins(session):
    """
    Auctions that were won and never paid for -- money the system is owed.
    Returns list[dict]: one row per unpaid win, largest debt first.
    """
    require_role(session, "Admin", "view the reports")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.auction_id,
                i.item_name,
                i.category,
                a.winner_login,
                a.current_highest_bid AS amount_owed,
                a.seller_login
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            LEFT JOIN payment p ON p.auction_id = a.auction_id
            WHERE a.auction_status = 'Closed'
              AND a.winner_login IS NOT NULL
              AND p.payment_id IS NULL
            ORDER BY a.current_highest_bid DESC
            """
        ).fetchall()

    return rows


def active_auctions(session):
    """
    Every open auction with its bidding activity, hottest first.
    Returns list[dict]: one row per Active auction, highest current bid first.
    """
    require_role(session, "Admin", "view the reports")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.auction_id,
                i.item_name,
                i.category,
                a.seller_login,
                i.starting_price,
                a.current_highest_bid,
                COUNT(b.bid_id) AS bids_placed,
                COUNT(DISTINCT b.buyer_login) AS bidders
            FROM auction a
            JOIN item i ON i.item_id = a.item_id
            LEFT JOIN bid b ON b.auction_id = a.auction_id
            WHERE a.auction_status = 'Active'
            GROUP BY
                a.auction_id,
                i.item_name,
                i.category,
                a.seller_login,
                i.starting_price,
                a.current_highest_bid
            ORDER BY a.current_highest_bid DESC, bids_placed DESC
            """
        ).fetchall()

    return rows
