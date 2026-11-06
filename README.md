# RootMap - Cross-host Dependency Mapper

RootMap is a Linux-based system designed to discover, collect, and visualize service dependencies across multiple hosts within a network.

The system uses a centralized head node to manage connected Linux hosts, coordinate data collection, process reports, and display discovered relationships through a web-based dashboard.

## Project Goals

- Dependency Mapping: Identify and visualize relationships between services running across Linux hosts.
- Automated Collection: Collect system and service information through scheduled collection scripts.
- Centralized Management: Manage connected hosts, collection schedules, and reports from a single dashboard.
- Script Synchronization: Maintain consistent collection script versions across connected hosts.
- Security: Authenticate clients and protect communication between hosts and the head node.

## Repo Structure

```text
rootmap/
├── backend/
├── client/
├── frontend/
├── scripts/
├── deploy/
├── docs/
└── .github/
```

## Environment Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Git
- Docker Desktop (for the local PostgreSQL setup below)

### Initial setup only

Run this once in PowerShell from the repository root to install dependencies:

```powershell
Set-Location backend; uv sync; Set-Location ..\client; uv sync; Set-Location ..\frontend; npm install; Set-Location ..
```

Start Docker Desktop, then create the local PostgreSQL container and data
volume:

```powershell
docker run --name rootmap-db -e POSTGRES_USER=rootmap -e POSTGRES_PASSWORD=rootmap -e POSTGRES_DB=rootmap -p 127.0.0.1:5432:5432 -v rootmap-pgdata:/var/lib/postgresql/data -d postgres:17
```

### Start the dashboard

Start the existing database container:

```powershell
docker start rootmap-db
```

In one PowerShell terminal from the repository root, start the backend:

```powershell
Set-Location backend; $env:DATABASE_URL = 'postgresql://rootmap:rootmap@127.0.0.1:5432/rootmap'; uv run uvicorn main:app --reload
```

In a second PowerShell terminal from the repository root, start the frontend:

```powershell
Set-Location frontend; npm run dev
```

### Run backend tests

From the repository root:

```powershell
Set-Location backend; uv run pytest
```

Tests that need PostgreSQL are skipped unless `TEST_DATABASE_URL` is set.

### Stop or reset the local setup

Press **Ctrl+C** in the backend and frontend terminals to stop the apps. Stop
the database container with:

```powershell
docker stop rootmap-db
```

Start the database again with `docker start rootmap-db`.

To clear all demo tables and data but keep the container and volume:

1. Stop the backend with **Ctrl+C**.
2. Run this command in PowerShell:

   ```powershell
   docker exec rootmap-db psql -U rootmap -d rootmap -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION rootmap;"
   ```

3. Start the backend again. It recreates the tables and initial **Admin** /
   **Password** login.

To delete the container and its database files too, stop it first, then run:

```powershell
docker rm rootmap-db; docker volume rm rootmap-pgdata
```
