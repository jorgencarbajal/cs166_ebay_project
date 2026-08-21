"""
Registration and login.

register() inserts a new row into users and returns a Session; login() checks credentials and returns a Session. Both raise from errors.py on failure -- LoginTaken and BadCredentials respectively.

New accounts are always Buyer. The schema defaults the column and only an Admin can change a role afterwards, so register() deliberately accepts no role argument. Called only from menus/__init__.py, before any role menu exists to dispatch to.
"""

# dataclass is a decorator that writes the boring parts of a class for you -- the __init__ that assigns the fields, an __eq__ that compares them, and a __repr__ that prints them. Without it, Session would be fifteen lines of self.login = login boilerplate.
from dataclasses import dataclass

# We import psycopg here for one reason only: to name the specific exception the database raises when a UNIQUE constraint is broken, so we can turn it into our own LoginTaken. This module never opens a connection itself -- that is db.get_connection()'s job.
import psycopg

# The dot means "from this same package" -- src/db.py, not some installed library called db. Without the dot Python would search the installed packages first and fail.
from .db import get_connection

# Import only the two exceptions this module can raise. Importing the whole errors module would work too, but naming them makes it obvious at the top of the file what can go wrong in here.
from .errors import BadCredentials, LoginTaken, NotAuthorized


# frozen=True makes the instance read-only: session.role = "Admin" raises an error instead of silently succeeding. That matters because a Session is the app's answer to "who is this and what may they do", and nothing downstream should be able to edit that answer after the fact.
@dataclass(frozen=True)
class Session:
    """
    Who is currently using the application.

    Two fields and no behaviour. This is not a database session and holds no connection -- db.get_connection() opens a fresh one per call. It is simply the app's memory of who logged in, created by register() or login(), held in a variable in menus/__init__.py for as long as the person is using the program, and thrown away on logout.

    Every feature function takes one of these rather than a bare login string, so identity always traces back to an actual login and a caller cannot act as someone else by passing a different username.
    """

    # The username, which is also the primary key of the users table.
    login: str

    # 'Buyer', 'Seller', or 'Admin' -- the schema's CHECK constraint guarantees it is one of those three.
    role: str


def require_role(session, required_role, action):
    """
    Stop a user from doing something their role does not permit.

    Called at the top of any feature function that is restricted -- listing an item is Sellers only, placing a bid is Buyers only, promoting a user is Admins only. It either returns quietly or raises, so the calling code can simply run it as a statement and carry on:

        require_role(session, "Seller", "list an item")

    Roles are checked here in Python rather than in SQL because the database can only enforce role rules on rows that reference a role column. Refusing to even show a menu option is an application concern.

    Args:
        session (Session): the logged-in user.
        required_role (str): 'Buyer', 'Seller', or 'Admin'.
        action (str): a short verb phrase used to build the error message, as in "Only Sellers can list an item."

    Raises:
        NotAuthorized: if the session's role is not the required one.
    """
    # A plain string comparison. Roles are stored exactly as 'Buyer' / 'Seller' / 'Admin' by the schema's CHECK constraint, so there is no case-folding to worry about.
    if session.role != required_role:
        # NotAuthorized builds the finished sentence itself from these two pieces -- see errors.py.
        raise NotAuthorized(action, required_role)


def register(login, password, phone_num, address, favorite_category=None):
    """
    Create a new account and return the Session it is already logged in on.

    The new user is always a Buyer. The role column is left out of the INSERT entirely so the schema's DEFAULT 'Buyer' applies -- writing it explicitly here would mean two places to change if that default ever moved. Promotion to Seller is an Admin action, handled in users.py.

    Registration logs you straight in rather than printing "account created, now sign in": the INSERT succeeding is already proof the credentials are valid, so asking for them a second time is a wasted round trip.

    Passwords are stored as plain text. That is a deliberate, documented limitation -- sql/seed.sql seeds plain-text passwords, so hashing here would lock us out of every seeded account.

    Args:
        login (str): the desired username, up to 50 characters.
        password (str): plain text, up to 100 characters.
        phone_num (str): required by the schema, NOT NULL.
        address (str): required by the schema, NOT NULL.
        favorite_category (str | None): optional -- the only nullable column on users.

    Returns:
        Session: the new user, with role 'Buyer'.

    Raises:
        LoginTaken: if that username already exists.
    """
    # The whole INSERT is wrapped in try/except so we can translate one specific database error into one of ours. Everything else -- a dead connection, a typo in this SQL -- is left alone to crash loudly, because those are bugs, not things the user did.
    try:
        # "with" gives us the connection and closes it afterwards whatever happens. psycopg 3 also commits the transaction on a clean exit and rolls it back if an exception escapes, so there is no explicit conn.commit() anywhere in this project.
        with get_connection() as conn:
            # %s is psycopg's placeholder, and the tuple below fills them in. The driver escapes each value as it goes, which is what makes SQL injection impossible -- never build this string with an f-string or +.
            conn.execute(
                """
                INSERT INTO users (login, password, phone_num, address, favorite_category)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (login, password, phone_num, address, favorite_category),
            )

    # UniqueViolation is what Postgres raises when a row breaks a PRIMARY KEY or UNIQUE constraint. On this table it can only mean the login already exists, since login is the primary key.
    except psycopg.errors.UniqueViolation:
        # "from None" hides the psycopg traceback underneath ours. The user does not need to see a database stack trace to learn that a username is taken.
        raise LoginTaken(login) from None

    # No SELECT needed to build this. We know the login because we just wrote it, and we know the role because we deliberately let the column default fire.
    return Session(login=login, role="Buyer")


def login(login, password):
    """
    Check a username and password, and return the Session on success.

    One query does both jobs: matching the row and checking the password. A wrong username and a wrong password are therefore indistinguishable from the outside, which is intentional -- BadCredentials never says which half was wrong, so nobody can use the login screen to discover valid usernames.

    Args:
        login (str): the username to log in as.
        password (str): plain text, compared directly.

    Returns:
        Session: the logged-in user, carrying the role read from the database.

    Raises:
        BadCredentials: if no row matches both values.
    """
    # Note that the parameter "login" shadows this function's own name inside the body. Harmless here, since nothing in this function needs to call itself, and it keeps the argument named after the column it matches.
    with get_connection() as conn:
        # Select only what the Session needs. Pulling password or address as well would put the password in a variable for no reason.
        row = conn.execute(
            """
            SELECT login, role
            FROM users
            WHERE login = %s AND password = %s
            """,
            (login, password),
        ).fetchone()

    # fetchone() returns None when the query matched nothing at all, rather than raising. That None is the entire failure case: no row means no such username, or the right username with the wrong password.
    if row is None:
        # BadCredentials takes no arguments -- the vague message is baked into the class.
        raise BadCredentials()

    # row is a dict rather than a tuple because db.py sets dict_row as the row factory, so these are column names, not positions.
    return Session(login=row["login"], role=row["role"])
