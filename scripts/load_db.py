"""
Build the database from the .sql files in sql/.

Run by hand, never imported. This is the only file in the project allowed to be destructive: sql/schema.sql opens with six DROP TABLE ... CASCADE statements, so running this throws away every row you have.

    .venv/bin/python scripts/load_db.py                  # asks before dropping
    .venv/bin/python scripts/load_db.py --yes            # skips the prompt
    .venv/bin/python scripts/load_db.py --dry-run        # shows the plan, touches nothing
    .venv/bin/python scripts/load_db.py --yes --bulk     # + sql/bulk_seed.sql, for issue #17
    .venv/bin/python scripts/load_db.py --yes --bulk --skip-indexes   # the "before" measurement

You run this once to create the database, then leave it alone. Data you create through the app persists because nothing else ever drops a table.

TWO FLAGS EXIST FOR THE TUNING WORK, and neither belongs in normal use.

--bulk adds sql/bulk_seed.sql, which is roughly 29,000 bids. Without it you get the small readable dataset from seed.sql, and that is what the demo runs against -- browse showing four open auctions rather than four and a half thousand is the entire reason the two dataset files are separate.

--skip-indexes omits sql/indexes.sql. Measuring what an index is worth means running the same query twice, once without it and once with, so there has to be a way to build the data and deliberately not build the indexes. The other half of that loop is applying indexes.sql by hand afterwards:

    cs166_psql -d jcarb044_DB -f sql/indexes.sql
"""

# argparse builds the --yes / --dry-run command line flags and the --help text for us.
import argparse

# pathlib gives us Path objects for filesystem paths -- cleaner than gluing strings together with slashes, and it works on both Windows and Linux.
from pathlib import Path

# sys is here for two things: sys.path (so we can import src/db.py, see below) and sys.exit (to stop with a non-zero exit code on failure).
import sys


# This file lives in scripts/, so its parent's parent is the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent

# src/ is not an installed package, so Python would not find "db" on its own. Putting the repo root at the front of sys.path lets "from src import db" work no matter which directory you launched the script from.
sys.path.insert(0, str(REPO_ROOT))

from src import db


# The .sql files that always run, in order. Order matters: extensions.sql alters tables that schema.sql creates, and seed.sql fills tables that must already exist.
SQL_FILES = [
    "schema.sql",
    "extensions.sql",
    "seed.sql",
]

# Added by --bulk. It goes after seed.sql but BEFORE indexes.sql, and both halves of that matter: it needs the sequences and the predictable logins seed.sql leaves behind, and inserting 29,000 rows into an already-indexed table means paying index maintenance on every single one.
BULK_FILE = "bulk_seed.sql"

# Always last, and omitted entirely by --skip-indexes. Indexes are built after the data for the reason above -- a bulk insert into an unindexed table is substantially faster, and the resulting index is better packed.
INDEX_FILE = "indexes.sql"


def files_to_run(with_bulk, with_indexes):
    """Assemble the ordered list of .sql filenames for this particular run."""
    names = list(SQL_FILES)

    if with_bulk:
        names.append(BULK_FILE)

    if with_indexes:
        names.append(INDEX_FILE)

    return names


def target_description():
    """Describe the database we are about to destroy, read straight from .env."""
    # Importing db already ran load_dotenv(), so the DB_* variables are in the environment by now.
    import os

    return "{user}@{host}:{port}/{name}".format(
        user=os.environ["DB_USER"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        name=os.environ["DB_NAME"],
    )


def sql_files(names):
    """Return the .sql files that actually have something in them, in run order."""
    found = []

    for name in names:
        path = REPO_ROOT / "sql" / name

        # A file we have not written yet is not an error -- seed.sql and indexes.sql are deliberately empty for now, so just skip them.
        if not path.exists():
            print("  skip  {:<16} (not found)".format(name))
            continue

        # .strip() removes whitespace, so a file containing only blank lines counts as empty too.
        if not path.read_text(encoding="utf-8").strip():
            print("  skip  {:<16} (empty)".format(name))
            continue

        found.append(path)
        print("  run   {:<16} ({:,} bytes)".format(name, path.stat().st_size))

    return found


def run_file(cursor, path):
    """Execute every statement in one .sql file."""
    # Reading the file at run time is the whole point: the .sql files are the source of truth, so if the server instance is lost these files rebuild it. Never paste schema into a Python string.
    sql = path.read_text(encoding="utf-8")

    # psycopg happily runs a whole file of semicolon-separated statements in a single execute(), as long as we are not passing parameters -- which we never are here.
    cursor.execute(sql)

    print("  done  {}".format(path.name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="show what would run, then stop")
    parser.add_argument("--bulk", action="store_true", help="also load sql/bulk_seed.sql (~29,000 bids, for issue #17)")
    # dest is spelled out because argparse would turn --skip-indexes into args.skip_indexes anyway -- naming it here makes that explicit rather than implied.
    parser.add_argument("--skip-indexes", dest="skip_indexes", action="store_true", help="do not run sql/indexes.sql, for the 'before' half of a tuning measurement")
    args = parser.parse_args(argv)

    # Say what we are aiming at before doing anything, so there is no ambiguity about which database is being wiped.
    print("\nTarget database: {}".format(target_description()))
    print("\nFiles:")
    files = sql_files(files_to_run(with_bulk=args.bulk, with_indexes=not args.skip_indexes))

    # Say out loud which dataset is being built. Loading the bulk data by accident the night before a demo would be a bad thing to discover on screen.
    if args.bulk:
        print("\n  --bulk: loading the large dataset. This is for measurement, not for the demo.")

    if args.skip_indexes:
        print("  --skip-indexes: indexes.sql will NOT run. Apply it by hand for the 'after' measurement.")

    if not files:
        print("\nNothing to run.")
        return 0

    if args.dry_run:
        print("\nDry run -- nothing was executed.")
        return 0

    # --yes exists so this can be re-run quickly during development without typing at a prompt every time.
    if not args.yes:
        print("\nThis DROPS every table listed in sql/schema.sql. All data will be lost.")
        answer = input("Type 'yes' to continue: ").strip().lower()

        if answer != "yes":
            print("Aborted.")
            return 1

    print()

    # "with conn:" wraps everything in a single transaction -- all the files commit together at the end, or a failure anywhere rolls the whole thing back and leaves the database exactly as it was. No half-built schema.
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            for path in files:
                run_file(cursor, path)

    print("\nDatabase ready.")
    return 0


# Entry point, not a test -- this script is meant to be run, and main() is what running it does. Use --dry-run to exercise the path-finding and .env reading without touching the database.
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ctrl+C at the confirmation prompt should be a clean exit, not a traceback.
        print("\nAborted.")
        sys.exit(1)
