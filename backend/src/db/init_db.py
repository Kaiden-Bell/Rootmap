"""Create all RootMap tables by running schema.sql.

Run from the backend/ directory:

    uv run python -m src.db.init_db
"""

from pathlib import Path

from src.db.connection import get_connection

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA_FILE.read_text())
    print(f"Applied {SCHEMA_FILE.name}")


if __name__ == "__main__":
    init_db()
