# Hoyoverse Graph

This repository is used to create a visualization of all the terms and entities found in the hoyoverse honkai games.

Search behavior and result-contract notes live in [docs/search.md](./docs/search.md).
Contributor and agent workflow standards live in [AGENTS.md](./AGENTS.md).

## API Documentation

- [API docs index](./docs/api/README.md)
- [Search API](./docs/api/search.md)
- [Graph API](./docs/api/graph.md)
- [Entity Detail API](./docs/api/entity-detail.md)
- [Deployment docs](./docs/deployment.md)

## Prerequisites

Use Node.js `v26.3.1` for the frontend work in this repository.

Recommended setup with `nvm`:

```bash
nvm install
nvm use
```

Verify your versions:

```bash
node --version
npm --version
```

## Environment Setup

Create local environment files from the checked-in examples:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Start local Postgres:

```bash
docker compose up -d
```

## Development

### Install pre-commit hooks

```bash
pre-commit install
```

### Run lint

```bash
ruff check .
```

### Run tests

```bash
pytest
```

### Run the backend

Create a virtual environment, install Python dependencies, and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m uvicorn api.main:app --reload
```

### Run the frontend

```bash
cd frontend
npm ci
npm run dev
```

## Frontend Development

Install dependencies:

```bash
cd frontend
npm ci
```

Start the development server:

```bash
npm run dev
```

Build the production bundle:

```bash
npm run build
```

Run lint:

```bash
npm run lint
```

Run tests:

```bash
npm test
```

### Frontend Testing Direction

Frontend smoke tests will use:

- Vitest
- React Testing Library
- jsdom

These tests are planned as lightweight coverage for core pages such as search,
graph, and entity detail. They run in CI and are required for merge.

### Current Merge Checks

Required checks today:

- `pytest`
- `ruff`
- `frontend-build`
- `frontend-lint`
- `frontend-test`

### Run all pre-commit checks

```bash
pre-commit run --all-files
```

## Empty Clone Checklist

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
cp .env.example .env
cp frontend/.env.example frontend/.env.local
docker compose up -d
python -m uvicorn api.main:app --reload
cd frontend && npm ci && npm run dev
```

## API (Entity Read Endpoint)

Run the API server:

```bash
python -m uvicorn api.main:app --reload
```

Read an entity by ID or slug:

```bash
curl http://127.0.0.1:8000/entities/ENT-0001
curl http://127.0.0.1:8000/entities/kiana-kaslana
```
