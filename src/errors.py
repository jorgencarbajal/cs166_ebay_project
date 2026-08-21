"""
The application's exception vocabulary.

One class per business rule the system enforces, all inheriting from AppError. They live together in this one file so a menu can catch a specific failure without importing five feature modules, and so the top-level loop in menus/__init__.py can catch AppError as a blanket "the user did something the rules forbid" and print it in red instead of crashing.

Some carry data with them. BidTooLow holds the current highest bid so the menu can say "must exceed $45.00" rather than "bid too low". Feature modules raise these; menu modules catch them. Nothing in here knows anything about terminals or printing.
"""


class AppError(Exception):
    """
    Base class for every rule this application enforces.

    Two reasons everything inherits from this. First, a menu can write `except AppError` and catch any business-rule failure in one line. Second, it draws a hard line between "the user did something the rules forbid" -- which we explain politely -- and a genuine bug like a typo in our SQL, which should not be swallowed.

    Every subclass passes a finished, readable sentence up to Exception, so str(e) is always safe to print straight to the screen.
    """


# AUTHENTICATION AND PERMISSIONS ----------------------------------------------------------------


class LoginTaken(AppError):
    """Someone tried to register a username that already exists."""

    def __init__(self, login):
        # Store the value on the exception as well as putting it in the message, in case a caller wants the raw data rather than the sentence.
        self.login = login
        # super().__init__() hands the message to the built-in Exception machinery, which is what makes str(e) return it.
        super().__init__(f"The username {login!r} is already taken. Try another.")


class BadCredentials(AppError):
    """Wrong username or wrong password."""

    def __init__(self):
        # Deliberately vague: saying "no such user" would tell an attacker which usernames exist.
        super().__init__("Incorrect username or password.")


class NotAuthorized(AppError):
    """The logged-in user's role does not permit this action."""

    def __init__(self, action, required_role=None):
        self.action = action
        self.required_role = required_role

        if required_role:
            super().__init__(f"Only {required_role}s can {action}.")
        else:
            # No role named means it is an ownership problem rather than a role problem -- editing someone else's listing, for example.
            super().__init__(f"You are not allowed to {action}.")


# LOOKUPS ---------------------------------------------------------------------------------------


class NotFound(AppError):
    """Asked for a row that does not exist. Covers auctions, items, users, payments, shipments."""

    def __init__(self, what, key):
        # `what` is the thing's name for the message ("auction"), `key` is the id or login that missed.
        self.what = what
        self.key = key
        super().__init__(f"No {what} found with id {key!r}.")


# BIDDING ---------------------------------------------------------------------------------------


class BidTooLow(AppError):
    """A bid did not beat what it had to beat."""

    def __init__(self, amount, minimum):
        self.amount = amount
        # `minimum` is whichever is higher: the auction's current highest bid, or the item's starting price. A fresh auction has current_highest_bid = 0, so the starting price is what matters there.
        self.minimum = minimum
        # :.2f prints a Decimal with exactly two decimal places, matching the NUMERIC(10,2) columns.
        super().__init__(f"Your bid of ${amount:.2f} must be greater than ${minimum:.2f}.")


class SelfBid(AppError):
    """A seller tried to bid on their own auction."""

    def __init__(self):
        super().__init__("You cannot bid on your own auction.")


class AuctionClosed(AppError):
    """Tried to bid on, or close, an auction that is already closed."""

    def __init__(self, auction_id):
        self.auction_id = auction_id
        super().__init__(f"Auction {auction_id} is closed and no longer accepts bids.")


class AuctionHasBids(AppError):
    """Tried to change something that stops being changeable once people have bid on it."""

    def __init__(self, item_id):
        self.item_id = item_id
        # Raised when a seller tries to edit starting_price mid-auction -- moving the goalposts after bids exist is indefensible.
        super().__init__(f"Item {item_id} already has bids, so its starting price cannot be changed.")


# PAYMENT AND SHIPPING --------------------------------------------------------------------------


class NotWinner(AppError):
    """Tried to pay for an auction this user did not win."""

    def __init__(self, auction_id):
        self.auction_id = auction_id
        super().__init__(f"You did not win auction {auction_id}, so you cannot pay for it.")


class AlreadyPaid(AppError):
    """Tried to pay twice. The schema's UNIQUE on payment.auction_id would block it anyway."""

    def __init__(self, auction_id):
        self.auction_id = auction_id
        super().__init__(f"Auction {auction_id} has already been paid for.")


class PaymentIncomplete(AppError):
    """Tried to ship something that has not been paid for yet."""

    def __init__(self, auction_id, status=None):
        self.auction_id = auction_id
        # `status` is the payment's current state ('Pending' or 'Failed') when a payment row exists at all.
        self.status = status

        if status:
            super().__init__(f"Payment for auction {auction_id} is {status!r}, not 'Completed'. It cannot ship yet.")
        else:
            super().__init__(f"Auction {auction_id} has no payment yet. It cannot ship until it is paid.")


# ADMIN ------------------------------------------------------------------------------------------


class RoleChangeBlocked(AppError):
    """
    An admin tried to change a role that the schema will not let us change.

    users carries UNIQUE (login, role) so item, auction, bid, and payment can foreign-key to (login, role) and pin it with a CHECK -- item.seller_role must equal 'Seller', bid.buyer_role must equal 'Buyer'. Those keys are ON UPDATE CASCADE, so changing a role rewrites the child rows and then trips the CHECK.

    Our policy is to refuse rather than to clean up. Postgres would refuse anyway; this just turns an unreadable constraint violation into a sentence.
    """

    def __init__(self, login, current_role, new_role, reason):
        self.login = login
        self.current_role = current_role
        self.new_role = new_role
        # `reason` names the blocking rows, e.g. "owns 3 items" or "has placed 12 bids".
        self.reason = reason
        super().__init__(f"Cannot change {login!r} from {current_role} to {new_role}: the account {reason}.")


class ItemInUse(AppError):
    """Tried to delete an item that an auction still points at."""

    def __init__(self, item_id, auction_id):
        self.item_id = item_id
        self.auction_id = auction_id
        # auction.item_id is ON DELETE RESTRICT, so Postgres blocks this. Same policy as role changes: refuse and explain.
        super().__init__(f"Item {item_id} cannot be deleted while auction {auction_id} exists. Remove the auction first.")
