"""The application's exception vocabulary."""


class AppError(Exception):
    """Base class for every rule this application enforces."""


class LoginTaken(AppError):
    """Someone tried to register a username that already exists."""

    def __init__(self, login):
        self.login = login
        super().__init__(f"The username {login!r} is already taken. Try another.")


class BadCredentials(AppError):
    """Wrong username or wrong password."""

    def __init__(self):
        super().__init__("Incorrect username or password.")


class NotAuthorized(AppError):
    """The logged-in user's role does not permit this action."""

    def __init__(self, action, required_role=None):
        self.action = action
        self.required_role = required_role

        if required_role:
            super().__init__(f"Only {required_role}s can {action}.")
        else:
            super().__init__(f"You are not allowed to {action}.")


class NotFound(AppError):
    """Asked for a row that does not exist."""

    def __init__(self, what, key):
        self.what = what
        self.key = key
        super().__init__(f"No {what} found with id {key!r}.")


class BidTooLow(AppError):
    """A bid did not beat what it had to beat."""

    def __init__(self, amount, minimum):
        self.amount = amount
        self.minimum = minimum
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
        super().__init__(f"Item {item_id} already has bids, so its starting price cannot be changed.")


class NotWinner(AppError):
    """Tried to pay for an auction this user did not win."""

    def __init__(self, auction_id):
        self.auction_id = auction_id
        super().__init__(f"You did not win auction {auction_id}, so you cannot pay for it.")


class AlreadyPaid(AppError):
    """Tried to pay twice."""

    def __init__(self, auction_id):
        self.auction_id = auction_id
        super().__init__(f"Auction {auction_id} has already been paid for.")


class PaymentIncomplete(AppError):
    """Tried to ship something that has not been paid for yet."""

    def __init__(self, auction_id, status=None):
        self.auction_id = auction_id
        self.status = status

        if status:
            super().__init__(f"Payment for auction {auction_id} is {status!r}, not 'Completed'. It cannot ship yet.")
        else:
            super().__init__(f"Auction {auction_id} has no payment yet. It cannot ship until it is paid.")


class RoleChangeBlocked(AppError):
    """An admin tried to change a role that the schema will not let us change."""

    def __init__(self, login, current_role, new_role, reason):
        self.login = login
        self.current_role = current_role
        self.new_role = new_role
        self.reason = reason
        super().__init__(f"Cannot change {login!r} from {current_role} to {new_role}: the account {reason}.")


class ItemInUse(AppError):
    """Tried to delete an item that an auction still points at."""

    def __init__(self, item_id, auction_id):
        self.item_id = item_id
        self.auction_id = auction_id
        super().__init__(f"Item {item_id} cannot be deleted while auction {auction_id} exists. Remove the auction first.")
