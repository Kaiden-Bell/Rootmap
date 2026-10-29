# Rootmap - Crosshost dependancy Maper

RootMap is a Linux-based system designed to discover, collect, and visualize service dependencies across multiple hosts within a network.

The system uses a centralized head node to manage connected Linux hosts, coordinate data collection, process reports, and display discovered relationships through a web-based dashboard.

## Project Goals

- Dependency Mapping: Identify and visualize relationships between services running across Linux hosts.

- Automated Collection: Collect system and service information through scheduled collection scripts.

- Centralized Management: Manage connected hosts, collection schedules, and reports from a single dashboard.

- Script Synchronization: Maintain consistent collection script versions across connected hosts.

- Security: Authenticate clients and protect communication between hosts and the head node.

## Repo Structure

```sh
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
### Preqs
- Python 3.12+
- uv
- Node.js and npm
- Git

### Backend setup

Run the following:
``` sh
    cd backend
    uv sync
    uv run uvicorn rootmap.main:app --reload
```

### Client setup

Run the following:
```sh
    cd client
    uv sync
```

### Frontend setup

Run the following:
```sh
    cd frontend
    npm install
    npm run dev
```