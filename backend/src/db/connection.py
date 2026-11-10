"""Postgres connector (Psycopg3) for Rootmap.

Usage:

    from src.db import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT host_id, host_name FROM hosts WHERE is_active = %s", (True,)
        ).fetchall()
        # rows is a list of dicts: [{"host_id": 1, "host_name": "web01"}, ...]
"""

import os
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

"""
    SET A DATABASE_URL ENV VARIABLE, WHETHER ITS A .ENV FILE OR TERMINAL.
    Example: 'export DATABASE_URL="postgresql://user:password@localhost:5432/rootmap'

    Set in install_backend.sh
"""
DEFAULT_DATABASE_URL = "postgresql://rootmap_user:12345@localhost:5432/rootmap_db"

load_dotenv()

def get_connection() -> psycopg.Connection:
    """Open a new connection. Rows return as dicts."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return psycopg.connect(url, row_factory=dict_row)
