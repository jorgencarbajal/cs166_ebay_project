"""
The bid table: placing bids and reading bid history.

The most constraint-heavy module here. A bid must beat both auction.current_highest_bid and the item's starting_price, the auction must still be Active, and a seller may not bid on their own auction -- each failure raises a specific error from errors.py.

Placing a bid is one transaction that locks the auction row with SELECT ... FOR UPDATE, inserts into bid, and updates auction.current_highest_bid. That denormalized column is the reason the lock exists: two buyers reading the same stale high bid could otherwise both pass validation. Used by menus/buyer.py, and its history() feeds the auction detail view in auctions.py.
"""

from .auth import require_role
from .db import get_connection
from .errors import AuctionClosed, BidTooLow, NotFound, SelfBid


def place(session, auction_id, amount):
    """
    Place a bid on an auction, or raise explaining why it is not allowed.

    This is the only write in the project that has to be atomic, so it is worth reading slowly. Three statements run inside one transaction: a locking SELECT that fetches the auction and the rules it has to satisfy, an INSERT into bid, and an UPDATE that moves auction.current_highest_bid up to the new amount.

    WHY THE LOCK EXISTS. auction.current_highest_bid is denormalized -- the same number lives in the bid table as the largest bid_amount for the auction, and on the auction row as a single column. Denormalized data is fast to read and easy to get wrong. Without a lock, two buyers bidding at the same instant would both read the same old high bid of $62, both decide their $65 clears it, and both insert. The second UPDATE overwrites the first, and now the auction says $65 while two separate $65 bids exist and nobody can say who is winning. SELECT ... FOR UPDATE prevents that: the first transaction to reach the auction row holds it until it commits, and the second waits there, then re-reads the row and sees $65 -- so its own $65 correctly fails validation.

    WHY THERE IS NO conn.commit(). `with get_connection() as conn:` commits when the block exits cleanly and rolls back if an exception escapes it. Every raise below therefore undoes the whole transaction and releases the lock, which is exactly the behaviour we want and is why the validation happens after the lock rather than before it.

    Args:
        session (auth.Session): the logged-in user. The bidder is session.login and is never passed in as a parameter, so a caller cannot bid as somebody else.
        auction_id (int): which auction to bid on.
        amount (decimal.Decimal): how much to bid. Comes from ui.prompt_decimal(), which is the single place in the project where typed text becomes money -- never build this with float().

    Returns:
        dict: the row that was just written, with keys bid_id, bid_amount and bid_timestamp, so the menu can confirm the bid by its real id and its real database timestamp rather than guessing.

    Raises:
        NotAuthorized: the user is not a Buyer.
        NotFound: no auction has that id.
        AuctionClosed: the auction exists but is no longer Active.
        SelfBid: the user is the seller of this auction.
        BidTooLow: the amount does not beat both floors.
    """
    # Buyers only, and this is not a style choice -- the schema physically cannot store the alternative. bid.buyer_role is CHECK (buyer_role = 'Buyer') and foreign-keys to users(login, role), so a bid row belonging to a Seller or an Admin cannot exist. Checking it here turns what would be an ugly psycopg IntegrityError into a sentence the user can read.
    require_role(session, "Buyer", "place a bid")

    with get_connection() as conn:
        # One query fetches everything the five rules need. The JOIN to item is here for starting_price alone -- the auction table does not know what the item originally asked for, and rule five needs it. The join cannot duplicate rows, because auction.item_id is UNIQUE and NOT NULL so every auction matches exactly one item.
        # FOR UPDATE OF a is the important part. Plain FOR UPDATE would lock the item row as well, which would needlessly block a seller editing that item's description. Naming the alias restricts the lock to the auction row, which is the only row two bidders actually contend over.
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

        # fetchone() returns None rather than raising when the query matched nothing, so a typo'd or invented auction id lands here. Note this runs before any of the rule checks -- there is no point asking whether a nonexistent auction is closed.
        if auction is None:
            raise NotFound("auction", auction_id)

        # RULE 1 -- the auction must still be Active. Auctions have no end time anywhere in the schema; the only thing that closes one is its seller choosing to, in issue #10. So this is a plain status check and not a comparison against the clock.
        if auction["auction_status"] != "Active":
            raise AuctionClosed(auction_id)

        # RULE 2 -- a seller may not bid on their own auction. Nothing in the schema forbids it, because seller_login and buyer_login are different columns on different tables and no constraint can see both at once. It has to be enforced here, in the application.
        if auction["seller_login"] == session.login:
            raise SelfBid()

        # RULE 3 -- the bid must beat BOTH floors, so the floor that matters is whichever is higher. This one line is the whole reason issue #7 is tricky.
        # A brand new auction has current_highest_bid = 0.00, because that is the column default and nobody has bid yet. Comparing against that alone would let a $0.01 bid win a $120 first edition. Comparing against starting_price alone would let a $46 bid beat an auction already sitting at $62. max() of the two is the only version that is right in both cases.
        # Both values arrive from psycopg as Decimal, because the columns are NUMERIC(10,2), so max() compares them exactly with no floating-point drift.
        minimum = max(auction["current_highest_bid"], auction["starting_price"])

        # Strictly greater, deliberately. Equalling the floor is not enough, which on a fresh auction means the first bid has to clear the starting price rather than match it -- $120.01 on a $120.00 item. One rule covering both floors is simpler to explain than two, and it is the rule BidTooLow already writes into its message: "must be greater than $120.00".
        if amount <= minimum:
            # BidTooLow carries both numbers so the menu can print the exact figure the user has to beat instead of a vague "too low". See errors.py.
            raise BidTooLow(amount, minimum)

        # Every rule passed, so write the bid. bid_id is omitted because sql/extensions.sql gave the column a DEFAULT nextval(...) -- the sequence fills it in, which is why no INSERT in this project ever names an id. bid_timestamp is omitted for the same reason: the schema defaults it to CURRENT_TIMESTAMP, and letting the database stamp it means the time is the server's, not the client machine's.
        # buyer_role is written out explicitly even though it too has a default. It is the visible half of the schema's role-pinning trick, and spelling it out here is a reminder of why require_role() had to run at the top of this function.
        bid = conn.execute(
            """
            INSERT INTO bid (auction_id, buyer_login, buyer_role, bid_amount)
            VALUES (%s, %s, 'Buyer', %s)
            RETURNING bid_id, bid_amount, bid_timestamp
            """,
            (auction_id, session.login, amount),
        ).fetchone()

        # Now move the denormalized column up to match. This is the second half of the pair the lock protects -- the INSERT above and this UPDATE must either both happen or neither, or the bid table and the auction table start disagreeing about who is winning.
        conn.execute(
            """
            UPDATE auction
            SET current_highest_bid = %s
            WHERE auction_id = %s
            """,
            (amount, auction_id),
        )

    # The transaction committed when the `with` block closed, and the lock released with it. Returning the RETURNING row rather than a bare True means the menu can confirm with the real id and the real server timestamp -- and it costs nothing, since the INSERT had to go to the database anyway.
    return bid


def history(session, auction_id):
    """
    Return every bid placed on one auction, highest first.

    Feeds the auction detail screen in issue #5, sitting underneath auctions.detail(). Read-only, unrestricted -- bid history is public, the same way it is on any real auction site, and hiding it would make the current high bid impossible to interpret.

    ORDER BY bid_amount DESC is both the leaderboard order and the chronological order at once, which is worth understanding rather than assuming. place() requires every bid to be strictly greater than the current highest, so within a single auction each new bid is larger than every bid before it -- amount and time increase together and sorting by either gives the same sequence. The amount is sorted on rather than the timestamp because it is the column the ordering actually means something about, and because it stays correct even for rows loaded straight from seed.sql, which were never checked by place().

    No join to item or auction. The screen above this table has already printed what the item is; repeating it on all eleven rows would be noise.

    Args:
        session (auth.Session): the logged-in user. Not used in the query.
        auction_id (int): which auction's bids to return.

    Returns:
        list[dict]: bid_id, buyer_login, bid_amount, bid_timestamp. Empty list if nobody has bid, which is a normal answer -- see auction 3 in seed.sql.
    """
    with get_connection() as conn:
        # No NotFound check for a missing auction. The menu calls auctions.detail() first and that raises on a bad id, so by the time this runs the auction is known to exist -- and an auction that exists with no bids has to return an empty list anyway, which is indistinguishable from what a bad id would produce here.
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

    Read-only, so there is no lock and no transaction to think about -- the opposite of place() in every way. It is also the first query in the project to join three tables: bid holds the amount and the time, auction holds the status and who won, and item holds the name, because "you bid $62 on auction 1" means nothing to a person and "you bid $62 on the Vintage Leather Jacket" means everything.

    No require_role() call. A Seller or an Admin cannot have placed a bid in the first place -- bid.buyer_role is pinned to 'Buyer' by the schema -- so this simply returns an empty list for them rather than refusing outright. Refusing to show someone an empty list would be rude, not secure.

    WHY THE CASE LIVES IN SQL. Each row comes back already labelled Won, Lost, Leading, or Outbid. That label is derived entirely from columns this query has already fetched, so working it out in the database costs nothing extra, keeps the derivation next to the data it derives from, and leaves the menu with nothing to do but print. Recomputing it in Python would mean the same logic could drift out of step with the query feeding it.

    Every bid is listed, not just the most recent per auction. If you bid $50 and later $62 on the same auction, both rows appear -- and your own $50 is honestly labelled Outbid, because it was, by you. That is a real bid history rather than a summary.

    Args:
        session (auth.Session): the logged-in user. Their login is the only filter.

    Returns:
        list[dict]: keyed by column name, with an extra "outcome" key holding the label. Empty list if they have never bid, which is a normal answer and not an error.
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
