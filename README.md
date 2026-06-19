# Hoyoverse Graph

This repository is used to create a visualization of all the terms and entities found in the hoyoverse honkai games.

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

### Run all pre-commit checks

```bash
pre-commit run --all-files
```

## API (Entity Read Endpoint)

Run the API server:

```bash
uvicorn api.main:app --reload
```

Read an entity by ID or slug:

```bash
curl http://127.0.0.1:8000/entities/ENT-0001
curl http://127.0.0.1:8000/entities/kiana-kaslana
```
