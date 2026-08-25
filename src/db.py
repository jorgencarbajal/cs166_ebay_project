"""Database connection for the auction system."""

import os

import psycopg

from psycopg.rows import dict_row

from dotenv import load_dotenv


load_dotenv()


def get_connection():
    """
    Open and return a new connection to the auction database.
    Returns psycopg.Connection: a live connection whose rows come back as dicts.
    """
    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    dbname = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]

    return psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        row_factory=dict_row,
    )
