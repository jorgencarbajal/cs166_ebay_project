"""
Database connection for the auction system.

This module does exactly one thing: hand out a live connection to our PostgreSQL database. It never creates tables, never drops them, and never loads data -- importing this file is always safe. Setting up the schema is scripts/load_db.py's job, and that script gets its connection from here.

The application runs on the school server, on the same machine as Postgres, so there is no SSH tunnel and no port forwarding involved. The instance listens on 127.0.0.1 at the port in $PGPORT, which is what DB_HOST and DB_PORT in .env point at.

The one thing to remember: the Postgres instance is a user process, not a system service, so it does not survive a server reboot. If a connection fails, run cs166_db_status and start it with cs166_db_start before suspecting this code.
"""

# "os" is Python's standard library module for talking to the operating system. We only want one thing from it: os.environ, the dictionary of environment variables belonging to this process.
import os

# psycopg is the PostgreSQL driver -- the library that actually speaks the Postgres wire protocol. Note the name: this is psycopg 3. Do not copy code written for the older "psycopg2"; the API changed.
import psycopg

# A "row factory" decides what shape each result row comes back as. The default hands you a plain tuple, so you would read columns by position: row[0], row[1]. dict_row hands you a dictionary instead, so you read them by name: row["seller_id"]. Much harder to get wrong.
from psycopg.rows import dict_row

# python-dotenv reads a .env file off disk and copies its key=value pairs into os.environ, so the rest of the code can just read environment variables without caring where they came from.
from dotenv import load_dotenv


# Run load_dotenv() once, right here at import time -- the moment anything says "import db", the .env file is read and the DB_* variables land in os.environ. Calling it at module level (rather than inside the function) means the file is read one time, not once per connection.
load_dotenv()


def get_connection():
    """
    Open and return a new connection to the auction database.

    Every call opens a fresh connection rather than reusing one shared connection. That is deliberate: this is a single-user terminal app, so the cost of connecting is irrelevant, and a fresh connection means a database that went down shows up immediately as a clear failure instead of as a stale handle that mysteriously stops working.

    psycopg connections are context managers, so the caller can use either style:

        conn = get_connection()     # you close it yourself
        ...
        conn.close()

        with get_connection() as conn:      # closed automatically, and
            ...                             # committed / rolled back for you

    Returns:
        psycopg.Connection: a live connection whose rows come back as dicts.
    """
    # Read each setting from the environment, which load_dotenv() filled in from .env above. os.environ["KEY"] raises a KeyError if the variable is missing -- that is what we want. A missing DB_NAME should be a loud error naming the variable now, not a confusing connection failure later.
    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    dbname = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]

    # psycopg.connect() does the actual work: it opens a socket to the server, authenticates, and returns a Connection object.
    return psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        # Make every row a dict keyed by column name (see the dict_row import above).
        row_factory=dict_row,
    )
