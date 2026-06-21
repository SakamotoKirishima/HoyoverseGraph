# Hoyoverse Graph

This repository is used to create a visualization of all the terms and entities found in the hoyoverse honkai games.

Search behavior and result-contract notes live in [docs/search.md](./docs/search.md).

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

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

### Run all pre-commit checks

```bash
pre-commit run --all-files
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
