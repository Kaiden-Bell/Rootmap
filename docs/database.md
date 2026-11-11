# Database: running and testing

RootMap stores its data in **PostgreSQL**. The backend talks to it with
**psycopg 3** and plain SQL (no ORM). There are three pieces to know about,
all in `backend/src/db/`:

| File | What it does |
| --- | --- |
| `schema.sql` | Every table, constraint and index. This is the single source of truth for the schema. |
| `connection.py` | `get_connection()` opens a connection; rows come back as dicts. |
| `init_db.py` | Runs `schema.sql` against the database. Safe to re-run. |

All commands below are run from the `backend/` directory.

## 1. Setup Postgres

Pick **one**.

### Option A: Docker

```sh
docker run -d --name rootmap-db \
  -e POSTGRES_USER=rootmap -e POSTGRES_PASSWORD=rootmap -e POSTGRES_DB=rootmap \
  -p 5432:5432 -v rootmap-pgdata:/var/lib/postgresql/data \
  postgres:17
```

Day to day: `docker stop rootmap-db` / `docker start rootmap-db`.
The data lives in the `rootmap-pgdata` volume, so it survives restarts.

### Option B: Installed on your machine, we'll do this when we get access to proxmox for testing.

```sh
sudo apt install postgresql
sudo -u postgres psql -c "CREATE USER rootmap WITH PASSWORD 'rootmap';"
sudo -u postgres psql -c "CREATE DATABASE rootmap OWNER rootmap;"
```

## 2. Tell the backend where the database is

The backend reads the `DATABASE_URL` environment variable:

```sh
export DATABASE_URL="postgresql://rootmap:rootmap@localhost:5432/rootmap"
```

Format: `postgresql://USER:PASSWORD@HOST:PORT/DBNAME`

- If you don't set it, it falls back to `postgresql://localhost:5432/rootmap`.
- `export` only lasts for that terminal. Put the line in your shell profile
  (e.g. `~/.bashrc`) to keep it.
- A `.env` file is **not** loaded automatically; the backend only reads real
  environment variables.

## 3. Create the tables

```sh
uv run python -m src.db.init_db
```

You should see `Applied schema.sql`. Check it worked:

```sh
# Docker
docker exec rootmap-db psql -U rootmap -c '\dt'
# Installed locally
psql "$DATABASE_URL" -c '\dt'
```

You should see 10 tables.

## 4. Using the database in code

```python
from src.db import get_connection

with get_connection() as conn:
    conn.execute(
        "INSERT INTO hosts (host_ip, host_name, operating_system, os_release, subnet_mask)"
        " VALUES (%s, %s, %s, %s, %s)",
        ("10.0.0.1", "web01", "Ubuntu", "22.04.3 LTS (Jammy Jellyfish)", 24),
    )
    hosts = conn.execute(
        "SELECT host_id, host_name FROM hosts WHERE is_active = %s", (True,)
    ).fetchall()
    # [{'host_id': 1, 'host_name': 'web01'}]
```

Things to remember:

- The `with` block **commits** when it finishes and **rolls back** if an
  exception is raised. Without the `with`, nothing is saved until you call
  `conn.commit()`.
- **Always pass values as the second argument** with `%s` placeholders, as
  above. Never build SQL with f-strings or `+`; that allows SQL injection.
  (`%s` is used for every type, including numbers. It is not Python string
  formatting.)
- Table and column names can't be placeholders. If you need a dynamic one, use
  `psycopg.sql.Identifier` (see the psycopg docs).

## 5. Running the tests

```sh
uv run pytest
```

With no database configured this runs the **9 tests that don't need Postgres**
and **skips the other 18** (they show as `s`). To run everything, give the tests
a database:

```sh
DATABASE_URL="$DATABASE_URL" uv run pytest
```

Expected: `27 passed`.

This is safe to point at your dev database. Each database test creates its own
temporary schema (`test_<random>`), builds the tables inside it, and drops it
afterwards, so your real tables and data are never touched.

If `DATABASE_URL` is set but the database is unreachable, the tests
**fail** rather than skip, so a broken setup doesn't go unnoticed.

| Test file | Needs Postgres? | Covers |
| --- | --- | --- |
| `tests/test_schema_file.py` | No | `schema.sql` is well-formed: expected tables, `IF NOT EXISTS`, FK ordering, FK indexes. |
| `tests/test_connection.py` | No | `get_connection()` / `init_db()` wiring, with psycopg mocked. |
| `tests/test_schema_db.py` | Yes | The schema actually works: defaults, NOT NULL / UNIQUE / FK rules, cascade deletes, commit/rollback. |

## 6. Changing the schema

There are no migrations yet. `schema.sql` only uses `CREATE ... IF NOT EXISTS`,
so editing a table definition **will not change a table that already exists**.

For now, while the data is just test data:

1. Edit `src/db/schema.sql`.
2. Reset your dev database and re-create it:

   ```sh
   # Docker
   docker exec rootmap-db psql -U rootmap -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
   # Installed locally
   psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'

   uv run python -m src.db.init_db
   ```
3. Update the tests if behaviour changed, and run `uv run pytest`.

> This **deletes all data** in the database. Don't do it once real data matters;
> at that point we should add proper migrations.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `connection refused` on port 5432 | Postgres isn't running (`docker start rootmap-db`), or `DATABASE_URL` points at the wrong host/port. |
| `password authentication failed` | Wrong user/password in `DATABASE_URL`. |
| `database "rootmap" does not exist` | Create it (`CREATE DATABASE rootmap;`) or fix the name in `DATABASE_URL`. |
| `port is already allocated` when starting Docker | Another Postgres is on 5432. Stop it, or use `-p 5433:5432` and put `5433` in `DATABASE_URL`. |
| `ModuleNotFoundError: No module named 'src'` | Run commands from `backend/`, not the repo root. |
| 18 tests skipped | `DATABASE_URL` isn't set (see section 5). |
