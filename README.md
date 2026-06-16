# Hoyoverse Graph

This repository is used to create a visualization of all the terms and entities found in the hoyoverse honkai games.

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
