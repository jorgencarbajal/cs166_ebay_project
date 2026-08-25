"""Registration and login."""

from dataclasses import dataclass

import psycopg

from .db import get_connection

from .errors import BadCredentials, LoginTaken, NotAuthorized


@dataclass(frozen=True)
class Session:
    """Who is currently using the application."""

    login: str

    role: str


def require_role(session, required_role, action):
    """Stop a user from doing something their role does not permit."""
    if session.role != required_role:
        raise NotAuthorized(action, required_role)


def register(login, password, phone_num, address, favorite_category=None):
    """
    Create a new account and return the Session it is already logged in on.
    Returns session: the new user, with role 'Buyer'.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (login, password, phone_num, address, favorite_category)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (login, password, phone_num, address, favorite_category),
            )

    except psycopg.errors.UniqueViolation:
        raise LoginTaken(login) from None

    return Session(login=login, role="Buyer")


def login(login, password):
    """
    Check a username and password, and return the Session on success.
    Returns session: the logged-in user, carrying the role read from the database.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT login, role
            FROM users
            WHERE login = %s AND password = %s
            """,
            (login, password),
        ).fetchone()

    if row is None:
        raise BadCredentials()

    return Session(login=row["login"], role=row["role"])
