"""
The application. Run this to use the auction system.

    .venv/bin/python main.py            # on the server
    .venv/Scripts/python.exe main.py    # on Windows

This file is deliberately tiny. It checks the database is reachable, hands control to menus.run(), and catches the two things that should end the program rather than be shown as a menu message. Everything else -- the login gate, the role menus, every feature -- lives under src/.

Two failures are handled here and nowhere else:

    OperationalError    Postgres is not answering. Almost always means the instance is down, so the message says how to start it. Checked once up front so a dead database is reported before anyone types a password rather than after.
    KeyboardInterrupt   Ctrl+C. Ends the program quietly instead of printing a traceback over the interface.

Business-rule failures are not handled here. Those are AppError, they are normal, and menus/__init__.py catches them so the user stays in the menu. Anything else reaching this file is a genuine bug and is allowed to crash with its traceback intact, which is what we want while we are still building.
"""

import sys

import psycopg

from src import ui
from src.db import get_connection
from src import menus


def check_database():
    """
    Confirm Postgres is reachable before showing the interface.

    One trivial query. SELECT 1 asks the database for nothing at all -- it just proves the connection opened, authenticated, and got an answer back, which is everything we need to know.

    Returns:
        bool: True if the database answered, False if it did not (having already explained why).
    """
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")

    # OperationalError covers the whole family of "could not talk to the server" problems: refused connection, timeout, authentication failure, missing database.
    except psycopg.OperationalError as e:
        ui.blank()
        ui.error("Cannot reach the database.")
        ui.blank()
        # The driver's own message names the actual cause, and it is far more specific than anything we could write here.
        ui.info(str(e).strip())
        ui.blank()
        ui.info("Your Postgres instance is a user process, not a service, so it does not survive a reboot.")
        ui.info("Check it with cs166_db_status and start it with cs166_db_start, then try again.")
        return False

    # KeyError comes from db.py reading os.environ, and means a DB_* line is missing from .env entirely -- a different problem with a different fix, so it gets its own message.
    except KeyError as e:
        ui.blank()
        ui.error(f"Missing {e} in your .env file.")
        ui.info("Copy .env.example to .env and fill in your own values -- see README section 1.8.")
        return False

    return True


def main():
    ui.blank()
    ui.heading("Online Auction and Bidding System")

    if not check_database():
        # Non-zero tells the shell this did not work, which matters if anyone ever runs this from a script.
        return 1

    menus.run()

    ui.blank()
    ui.info("Goodbye.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    # Ctrl+C anywhere in the program lands here. Without this the user gets a traceback for doing something completely reasonable.
    except KeyboardInterrupt:
        ui.blank()
        ui.warn("Interrupted.")
        # 130 is the conventional exit code for "killed by Ctrl+C" on Unix.
        sys.exit(130)
