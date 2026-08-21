"""
Prove the whole stack actually works, in one command.

    .venv/bin/python scripts/smoke.py                # every section
    .venv/bin/python scripts/smoke.py --only auth    # just one section
    .venv/bin/python scripts/smoke.py --list         # show the section names and exit

Three jobs. Telling a new teammate their setup is correct without making them read code, catching a broken .env or a stopped Postgres instance before it wastes an hour, and re-checking every module after a git pull.

This is the counterpart to scripts/ui_demo.py. That one needs no database and proves the interface looks right; this one needs a database and proves the code underneath it behaves right.

It writes exactly one row -- a throwaway user named smoke_test_user -- and deletes it both before and after the auth section, so it is safe to run repeatedly and safe to run mid-demo. It touches nothing else and drops nothing. That is what separates it from scripts/load_db.py, which is genuinely destructive.

Exit code is 0 if every check passed and 1 if any failed, so it can be trusted in a script or a CI job later.

Add a section per module as the modules land: a list of (label, function) pairs, a name in SECTIONS, done.
"""

import argparse
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent

# src/ is not an installed package, so Python would not find it on its own. Putting the repo root at the front of sys.path lets "from src import ..." work no matter which directory you launched the script from.
sys.path.insert(0, str(REPO_ROOT))

from src import auth, ui
from src.db import get_connection
from src.errors import BadCredentials, LoginTaken, NotAuthorized


# The throwaway account this script creates and destroys. Deliberately unlike anything sql/seed.sql will produce, so there is no chance of deleting real data.
SMOKE_LOGIN = "smoke_test_user"
SMOKE_PASSWORD = "smoke-pw"

# The six tables sql/schema.sql creates. Listed here so a partial or failed load_db.py run is reported as a missing table rather than as a confusing SQL error three checks later.
EXPECTED_TABLES = ["users", "item", "auction", "bid", "payment", "shipment"]

# The five sequences sql/extensions.sql adds -- one per numeric-PK table. users is absent on purpose: its primary key is the login string, so it needs no sequence.
EXPECTED_SEQUENCES = ["item_id_seq", "auction_id_seq", "bid_id_seq", "payment_id_seq", "shipment_id_seq"]


# HELPERS ----------------------------------------------------------------------------------------


def target_description():
    """The database this run is about to talk to, printed up front so nobody debugs the wrong one."""
    return "{user}@{host}:{port}/{name}".format(
        user=os.environ["DB_USER"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        name=os.environ["DB_NAME"],
    )


def run_check(label, function):
    """
    Run one check and report it, returning True if it passed.

    Checks signal failure by raising. An AssertionError means the code ran but produced the wrong answer, which is a real finding and gets reported plainly. Any other exception means the code blew up somewhere we did not expect, so the exception type is included -- psycopg.OperationalError there almost always means the Postgres instance is down.

    Nothing is allowed to escape this function, because one broken check should not stop the other twenty from running.
    """
    try:
        function()

    # assert statements raise this. The message after the comma in an assert becomes str(e).
    except AssertionError as e:
        ui.error("{}\n    expected: {}".format(label, e))
        return False

    # Anything else is an unexpected crash rather than a wrong answer, so name the exception type to make the cause obvious.
    except Exception as e:
        ui.error("{}\n    {}: {}".format(label, type(e).__name__, e))
        return False

    ui.success(label)
    return True


def delete_smoke_user():
    """
    Remove the throwaway account, whether or not it exists.

    DELETE of a row that is not there is not an error in SQL -- it simply affects zero rows -- so this needs no existence check and is safe to call before the checks as well as after. Running it first matters: an earlier run that crashed halfway would otherwise leave the row behind and make register() fail with LoginTaken forever.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE login = %s", (SMOKE_LOGIN,))


# SECTION: DATABASE ------------------------------------------------------------------------------


def check_connection_opens():
    with get_connection() as conn:
        row = conn.execute("SELECT version() AS version").fetchone()

    assert row["version"].startswith("PostgreSQL"), "a version string beginning 'PostgreSQL', got {!r}".format(row["version"])


def check_tables_exist():
    with get_connection() as conn:
        # information_schema is the SQL standard's own catalogue of what exists in a database. 'public' is the default schema our tables live in; filtering on it keeps Postgres' internal tables out of the answer.
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        ).fetchall()

    # A set makes the "is it in there" test below instant and order-independent, which matters because SQL makes no promises about row order without an ORDER BY.
    found = {row["table_name"] for row in rows}
    missing = [name for name in EXPECTED_TABLES if name not in found]

    assert not missing, "all six tables, missing {} -- run scripts/load_db.py".format(", ".join(missing))


def check_sequences_exist():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema = 'public'
            """
        ).fetchall()

    found = {row["sequence_name"] for row in rows}
    missing = [name for name in EXPECTED_SEQUENCES if name not in found]

    assert not missing, "all five sequences, missing {} -- sql/extensions.sql did not load".format(", ".join(missing))


def check_ids_generate_themselves():
    """The whole point of sql/extensions.sql: an INSERT that omits the id still gets one."""
    with get_connection() as conn:
        # nextval() pulls the next number straight from the sequence without needing a row to insert, so this proves the sequence works without leaving anything behind in item.
        row = conn.execute("SELECT nextval('item_id_seq') AS id").fetchone()

    assert isinstance(row["id"], int), "an integer from nextval(), got {!r}".format(row["id"])


DATABASE_CHECKS = [
    ("Connection opens and Postgres answers", check_connection_opens),
    ("All six tables exist", check_tables_exist),
    ("All five sequences exist", check_sequences_exist),
    ("Sequences hand out ids", check_ids_generate_themselves),
]


# SECTION: AUTH ----------------------------------------------------------------------------------
#
# These run in order and depend on each other -- register() has to succeed before login() has anything to find. That is why they are a list rather than independent tests: this is a smoke test, not a unit test suite.


def check_register_returns_a_buyer_session():
    session = auth.register(SMOKE_LOGIN, SMOKE_PASSWORD, "555-0100", "1 Smoke Test Lane")

    assert session.login == SMOKE_LOGIN, "login {!r}, got {!r}".format(SMOKE_LOGIN, session.login)
    # Not written by register() -- this is the schema's DEFAULT 'Buyer' firing, which is exactly what we want to confirm.
    assert session.role == "Buyer", "role 'Buyer' from the schema default, got {!r}".format(session.role)


def check_registered_user_is_in_the_database():
    with get_connection() as conn:
        row = conn.execute("SELECT login, role, address FROM users WHERE login = %s", (SMOKE_LOGIN,)).fetchone()

    assert row is not None, "a users row for {!r}, found none -- register() returned a Session without committing".format(SMOKE_LOGIN)
    assert row["address"] == "1 Smoke Test Lane", "the address we passed in, got {!r}".format(row["address"])


def check_login_succeeds_with_correct_credentials():
    session = auth.login(SMOKE_LOGIN, SMOKE_PASSWORD)

    assert session.login == SMOKE_LOGIN, "login {!r}, got {!r}".format(SMOKE_LOGIN, session.login)
    assert session.role == "Buyer", "role 'Buyer' read back from the database, got {!r}".format(session.role)


def check_duplicate_registration_is_refused():
    try:
        auth.register(SMOKE_LOGIN, "different-pw", "555-0199", "2 Smoke Test Lane")

    except LoginTaken:
        # The success path. Getting here means the UNIQUE constraint fired and register() translated it.
        return

    # Reaching this line means no exception was raised at all, which would mean two rows now share a primary key.
    assert False, "LoginTaken for a username that already exists, but the second register() succeeded"


def check_wrong_password_is_refused():
    try:
        auth.login(SMOKE_LOGIN, "not-the-password")
    except BadCredentials:
        return

    assert False, "BadCredentials for a wrong password, but login() returned a Session"


def check_unknown_user_is_refused():
    try:
        auth.login("no_such_user_anywhere", "anything")
    except BadCredentials:
        return

    assert False, "BadCredentials for a username that does not exist, but login() returned a Session"


def check_require_role_allows_a_match():
    # Built by hand rather than fetched, because require_role() never touches the database -- it only reads the two fields on the Session.
    session = auth.Session(login=SMOKE_LOGIN, role="Buyer")
    auth.require_role(session, "Buyer", "place a bid")


def check_require_role_blocks_a_mismatch():
    session = auth.Session(login=SMOKE_LOGIN, role="Buyer")

    try:
        auth.require_role(session, "Seller", "list an item")
    except NotAuthorized:
        return

    assert False, "NotAuthorized when a Buyer attempts a Seller action, but require_role() allowed it"


def check_session_cannot_be_edited():
    """frozen=True is what stops a caller quietly promoting itself to Admin halfway through a menu."""
    session = auth.Session(login=SMOKE_LOGIN, role="Buyer")

    try:
        session.role = "Admin"
    # FrozenInstanceError is a subclass of AttributeError, so catching the broader one avoids importing dataclasses here just for its name.
    except AttributeError:
        return

    assert False, "assigning to session.role to raise, but it was allowed"


AUTH_CHECKS = [
    ("register() returns a Buyer Session", check_register_returns_a_buyer_session),
    ("register() actually committed the row", check_registered_user_is_in_the_database),
    ("login() succeeds with the right password", check_login_succeeds_with_correct_credentials),
    ("register() refuses a taken username", check_duplicate_registration_is_refused),
    ("login() refuses a wrong password", check_wrong_password_is_refused),
    ("login() refuses an unknown username", check_unknown_user_is_refused),
    ("require_role() allows a matching role", check_require_role_allows_a_match),
    ("require_role() blocks a mismatched role", check_require_role_blocks_a_mismatch),
    ("Session cannot be modified after login", check_session_cannot_be_edited),
]


# RUNNER -----------------------------------------------------------------------------------------
#
# Each section is (key, title, checks, prepare, cleanup). prepare and cleanup are either a function or None -- auth needs both, and they are the same function, because deleting the throwaway user is how you both start clean and finish clean.

SECTIONS = [
    ("database", "Database and schema", DATABASE_CHECKS, None, None),
    ("auth", "Registration and login", AUTH_CHECKS, delete_smoke_user, delete_smoke_user),
]


def run_section(key, title, checks, prepare, cleanup):
    """Run one section and return (passed, failed)."""
    ui.heading(title)

    if prepare is not None:
        prepare()

    passed = 0
    failed = 0

    for label, function in checks:
        if run_check(label, function):
            passed += 1
        else:
            failed += 1

    # try/finally would be overkill -- run_check() already swallows everything a check can throw, so nothing can jump past this line.
    if cleanup is not None:
        cleanup()

    ui.blank()
    return passed, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check that the application works against a live database.")
    parser.add_argument("--only", metavar="SECTION", help="run a single section by name")
    parser.add_argument("--list", action="store_true", help="show the section names and exit")
    args = parser.parse_args(argv)

    if args.list:
        for key, title, checks, _prepare, _cleanup in SECTIONS:
            ui.info("{:<10} {} ({} checks)".format(key, title, len(checks)))
        return 0

    sections = SECTIONS

    if args.only:
        sections = [s for s in SECTIONS if s[0] == args.only]
        if not sections:
            ui.error("No section named {!r}. Try --list.".format(args.only))
            return 1

    ui.blank()
    # Printed before anything connects, so a failure on the first check can be read against the settings that caused it.
    ui.info("Target: {}".format(target_description()))
    ui.blank()

    total_passed = 0
    total_failed = 0

    for section in sections:
        passed, failed = run_section(*section)
        total_passed += passed
        total_failed += failed

    if total_failed:
        ui.error("{} passed, {} failed.".format(total_passed, total_failed))
        # A non-zero exit code is the shell's way of saying "this did not work", which is what lets this be trusted in a script later.
        return 1

    ui.success("{} checks passed.".format(total_passed))
    return 0


# Entry point, not a test. Everything below runs only when the file is executed directly.
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        ui.blank()
        ui.warn("Interrupted. The throwaway user may still exist -- run this again to clear it.")
        sys.exit(130)
