"""
Build the database from the .sql files in sql/.

Run by hand, never imported.

    .venv/bin/python scripts/load_db.py                  # asks before dropping
    .venv/bin/python scripts/load_db.py --yes            # skips the prompt
    .venv/bin/python scripts/load_db.py --dry-run        # shows the plan, touches nothing
    .venv/bin/python scripts/load_db.py --yes --bulk     # + sql/bulk_seed.sql, for issue #17
    .venv/bin/python scripts/load_db.py --yes --bulk --skip-indexes   # the "before" measurement
"""

import argparse
import sys
from pathlib import Path
from src import db


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SQL_FILES = [
    "schema.sql",
    "extensions.sql",
    "seed.sql",
]
BULK_FILE = "bulk_seed.sql"
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

        if not path.exists():
            print("  skip  {:<16} (not found)".format(name))
            continue

        if not path.read_text(encoding="utf-8").strip():
            print("  skip  {:<16} (empty)".format(name))
            continue

        found.append(path)
        print("  run   {:<16} ({:,} bytes)".format(name, path.stat().st_size))

    return found


def run_file(cursor, path):
    """Execute every statement in one .sql file."""
    sql = path.read_text(encoding="utf-8")

    cursor.execute(sql)

    print("  done  {}".format(path.name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="show what would run, then stop")
    parser.add_argument("--bulk", action="store_true", help="also load sql/bulk_seed.sql (~29,000 bids, for issue #17)")
    parser.add_argument("--skip-indexes", dest="skip_indexes", action="store_true", help="do not run sql/indexes.sql, for the 'before' half of a tuning measurement")
    args = parser.parse_args(argv)

    print("\nTarget database: {}".format(target_description()))
    print("\nFiles:")
    files = sql_files(files_to_run(with_bulk=args.bulk, with_indexes=not args.skip_indexes))

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

    if not args.yes:
        print("\nThis DROPS every table listed in sql/schema.sql. All data will be lost.")
        answer = input("Type 'yes' to continue: ").strip().lower()

        if answer != "yes":
            print("Aborted.")
            return 1

    print()

    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            for path in files:
                run_file(cursor, path)

    print("\nDatabase ready.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
