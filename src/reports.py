"""
The four admin reports: aggregate queries that span the whole database.

WHY THIS MODULE EXISTS AT ALL. Every other feature module is named after one table -- bids.py touches bid, items.py touches item -- because that keeps a feature easy to find. These four queries break that rule: each one spans three or four tables and belongs to none of them. Scattering them across auctions.py and users.py would put the same kind of work in two unrelated files and make neither one findable. So they live together, named after what they are rather than what they touch.

This is where the "SQL queries and reports" half of the grade is most visible. Everything else in the application is a lookup, an insert, or an update -- necessary, but not the part of a database course anyone is grading. These four are the queries that use the database as a database: GROUP BY, HAVING, aggregates, an outer join used deliberately, and an anti-join. Each docstring below names the technique it demonstrates, because that is the answer to "why did you write it that way" during the demo.

Every function is Admin-only, returns a list of dicts, and prints nothing -- the same contract as every other feature module. menus/admin.py renders them all through ui.page().
"""

from .auth import require_role
from .db import get_connection


def top_bidders(session):
    """
    Every Buyer, with how much bidding they have actually done, busiest first.

    DEMONSTRATES: LEFT JOIN, GROUP BY, three different aggregates, and a correlated subquery.

    The LEFT JOIN is the point of this query and is not decoration. A plain JOIN would silently drop any Buyer who has never bid -- and "which of my users are not engaging" is exactly the question an admin wants this report to answer. A LEFT JOIN keeps every Buyer and fills the missing side with NULLs, so a registered account with no activity shows as a row of zeros instead of vanishing. In the seed data that row is newbie1, which is a good thing to point at during the demo: it proves the join type was chosen rather than defaulted to.

    COUNT() is what turns those NULLs into zeros for free. COUNT(b.bid_id) counts non-NULL values, so a Buyer with no bids counts zero rather than one -- which is why it counts the column and not COUNT(*), since COUNT(*) counts rows and would return 1 for the single all-NULL row a LEFT JOIN produces. That distinction is the single most common mistake in this kind of query.

    auctions_won is a correlated subquery: it runs once per outer row and refers back to that row through u.login. A second LEFT JOIN to auction would have been wrong -- joining bid and auction to the same user at once multiplies the two sets together and every count comes out inflated. A subquery counts a second, unrelated thing without disturbing the first.

    Args:
        session (auth.Session): must be an Admin.

    Returns:
        list[dict]: one row per Buyer. highest_bid is None for a Buyer who has never bid.

    Raises:
        NotAuthorized: the user is not an Admin.
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

    DEMONSTRATES: GROUP BY on a joined column, SUM / AVG / MAX together, and HAVING.

    HAVING is the clause worth explaining, because it looks like a second WHERE and is not. WHERE filters individual rows before they are grouped; HAVING filters the finished groups after aggregation, which means HAVING can test an aggregate and WHERE cannot. Here the WHERE picks which auctions count as sales, and the HAVING throws away any category whose total came to nothing. Neither could do the other's job.

    Revenue is read from auction.current_highest_bid rather than from the payment table on purpose, and the difference matters: this reports what the auctions closed at, not what has been collected. The gap between the two is the whole subject of the next report.

    Args:
        session (auth.Session): must be an Admin.

    Returns:
        list[dict]: one row per category that has sold at least one item. Categories with no completed sales do not appear at all.

    Raises:
        NotAuthorized: the user is not an Admin.
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

    DEMONSTRATES: an anti-join. This is the most idiomatic pattern in the whole project and the one most worth being able to explain.

    The question is "which closed auctions have no matching payment row", and a plain JOIN cannot answer it, because a JOIN can only return rows that matched -- it has no way to hand back the ones that did not. The technique is to LEFT JOIN the table you are looking for absence in, which keeps every auction and fills payment's columns with NULL wherever nothing matched, and then filter on `p.payment_id IS NULL`. Because payment_id is the primary key and can never be NULL in a real row, a NULL there means one thing only: the outer join found nothing. That combination -- LEFT JOIN plus IS NULL on the right-hand key -- is what an anti-join is.

    The other spelling is `WHERE NOT EXISTS (SELECT 1 FROM payment p WHERE ...)`, which reads more directly and which PostgreSQL usually plans identically. The anti-join is used here because it is the form worth being able to recognise and because it keeps the payment columns available if this report ever needs to show a partial payment.

    In the seed data this finds exactly one row -- auction 5, won by buyer1 at $96.00 and never paid -- which is a row that was put in seed.sql specifically so this report would have something to find.

    Args:
        session (auth.Session): must be an Admin.

    Returns:
        list[dict]: one row per unpaid win, largest debt first. Empty list when everybody has paid, which is a normal answer.

    Raises:
        NotAuthorized: the user is not an Admin.
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

    DEMONSTRATES: LEFT JOIN with GROUP BY, and COUNT(DISTINCT ...) against a plain COUNT.

    The LEFT JOIN to bid is doing the same job it does in top_bidders() -- keeping the rows with nothing on the other side. An auction nobody has bid on yet is precisely the row an admin most wants to see in a "how is the site doing" report, and an inner join would drop it. In the seed data that is auction 3, which shows zero bids and a current high of 0.00 alongside a starting price of $120.00.

    The two count columns say different things and the difference is the interesting part. COUNT(b.bid_id) is how many bids were placed; COUNT(DISTINCT b.buyer_login) is how many people placed them. Three bids from one determined buyer and three bids from three different buyers are very different situations and the first number cannot tell them apart.

    Every non-aggregated column is listed in the GROUP BY. PostgreSQL would accept a shorter list here -- grouping by a table's primary key lets it infer the rest of that table's columns -- but writing them out is what the SQL standard requires and it keeps the query working if a column is ever moved between tables.

    Args:
        session (auth.Session): must be an Admin.

    Returns:
        list[dict]: one row per Active auction, highest current bid first.

    Raises:
        NotAuthorized: the user is not an Admin.
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
