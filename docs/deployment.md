# Deployment Planning

This document outlines a practical first deployment plan for the current
HoYoverse Graph monorepo.

## Recommended Initial Architecture

- Frontend: Vercel
- Backend: Render or Railway
- Database: Neon Postgres

### Why this split fits the current monorepo

- The frontend already lives in `frontend/` as a standalone Next.js app, which
  maps cleanly to a Vercel project with minimal setup.
- The backend is a standard FastAPI service with a single database dependency,
  which fits well on either Render or Railway without requiring Docker first.
- Neon provides managed Postgres with a strong developer workflow for branchable
  environments, which is useful for staging and production separation later.
- This split keeps hosting simple while matching the repo's current boundaries:
  one frontend app, one backend API, one Postgres database.
- It also avoids forcing containerization or a larger platform decision before
  the project needs it.

## Suggested Platform Shape

### Frontend on Vercel

- Create one Vercel project from the `frontend/` directory.
- Configure the root directory as `frontend`.
- Use Vercel for:
  - preview deployments on pull requests
  - staging deployment from a staging branch or project
  - production deployment from `main`

### Backend on Render or Railway

- Create one backend web service that runs the FastAPI app.
- Start command should be based on the current app entrypoint, for example:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

- Keep the backend separate from the frontend so each service can scale,
  restart, and roll back independently.

### Database on Neon

- Use Neon Postgres as the managed database.
- Start with one production database and one staging database or branch.
- Use platform-provided pooled connection strings where appropriate.

## Required Production Environment Variables

### Backend

Required by the current backend code:

- `DATABASE_URL`
  - Full Postgres connection string used by `api/db.py`
- `ALLOWED_ORIGINS`
  - Comma-separated list of frontend origins allowed to call the API
- `PORT`
  - Optional runtime port used by container platforms; defaults to `8000`
    when not provided

Recommended example:

```bash
DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
PORT=8000
```

Notes:

- The backend currently reads `DATABASE_URL` directly.
- `ALLOWED_ORIGINS` should be set explicitly in hosted environments rather than
  relying on local defaults.
- The backend container startup command reads `PORT` at runtime and falls back
  to `8000` when the hosting platform does not inject it.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and
  `POSTGRES_PORT` are useful for local setup, but the deployed app does not
  require them if `DATABASE_URL` is present.

### Frontend

Required by the current frontend code:

- `NEXT_PUBLIC_API_BASE_URL`
  - Public base URL for the deployed backend API

Example:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-backend-service.example.com
```

Important note:

- `NEXT_PUBLIC_API_BASE_URL` is a build-time value for the current Next.js
  frontend because `NEXT_PUBLIC_*` variables are embedded into the client bundle.
- For Docker-based frontend builds, provide this value during `docker build`.
- Changing only the container runtime environment will not rebuild already
  bundled client-side API URLs.

## Environment Configuration

Use the checked-in example files as templates only:

- backend local development: `.env.example`
- backend staging: `.env.staging.example`
- backend production: `.env.production.example`
- frontend local development: `frontend/.env.example`
- frontend staging: `frontend/.env.staging.example`
- frontend production: `frontend/.env.production.example`

Do not commit real `.env`, `.env.production`, or `.env.staging` files.

### Backend variables

- `DATABASE_URL`
  - Secret
  - Used by the FastAPI backend to connect to Postgres
  - Configure this in Neon and then copy the value into Render or Railway
    secret/environment settings
- `ALLOWED_ORIGINS`
  - Not secret
  - Comma-separated frontend origin list used for CORS
  - Configure separately in Render or Railway for staging and production
- `PORT`
  - Not secret
  - Usually provided automatically by Render or Railway
  - Keep `PORT=8000` only as a template/default example

### Frontend variables

- `NEXT_PUBLIC_API_BASE_URL`
  - Public
  - Embedded into the Next.js bundle at build time
  - Configure this in Vercel project settings or supply it as a Docker build arg
  - `NEXT_PUBLIC_*` values must never contain secrets

### Platform ownership

- Neon
  - source of truth for the backend `DATABASE_URL`
- Render or Railway
  - backend runtime configuration:
    - `DATABASE_URL`
    - `ALLOWED_ORIGINS`
    - platform-managed `PORT`
- Vercel
  - frontend build/runtime configuration:
    - `NEXT_PUBLIC_API_BASE_URL`

### Staging vs production

- Use separate `DATABASE_URL` values for staging and production
- Use separate `ALLOWED_ORIGINS` values for staging and production
- Use separate `NEXT_PUBLIC_API_BASE_URL` values for staging and production

Example production values:

```bash
# Backend
DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
ALLOWED_ORIGINS=https://<production-frontend-domain>
PORT=8000

# Frontend
NEXT_PUBLIC_API_BASE_URL=https://<production-backend-domain>
```

## Current Deployment Gaps To Address Before Go-Live

These are important deployment expectations for the current codebase:

- Backend CORS is environment-aware through `ALLOWED_ORIGINS`.
- If `ALLOWED_ORIGINS` is not set, the backend falls back to local development
  origins only:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- Production and staging environments should set explicit origin lists and
  should not rely on those local defaults.

## Staging vs Production Plan

### Staging

- Frontend:
  - Vercel preview deployments or a dedicated Vercel staging project
- Backend:
  - separate Render/Railway staging service
- Database:
  - separate Neon staging database or Neon branch

Staging goals:

- verify frontend-backend integration
- verify environment variables
- test migrations and data loading strategy
- smoke test search, graph, and entity detail pages against hosted services
- verify staging `ALLOWED_ORIGINS` only includes staging or preview frontend URLs

### Production

- Frontend:
  - Vercel production deployment
- Backend:
  - separate Render/Railway production service
- Database:
  - Neon production database

Production goals:

- stable public URL for frontend
- stable public API base URL
- protected production database credentials
- explicit rollback path for frontend and backend independently
- production `ALLOWED_ORIGINS` restricted to approved production frontend URLs

### Recommended separation

- Do not share the same database between staging and production.
- Do not point Vercel preview deployments at production data by default.
- Keep staging and production secrets separate across all platforms.
- Keep staging and production `ALLOWED_ORIGINS` values separate.

## Deployment Readiness Checklist

### Application readiness

- [ ] Backend CORS supports deployed frontend origins
- [ ] `DATABASE_URL` is configured in the backend host
- [ ] `NEXT_PUBLIC_API_BASE_URL` is configured in Vercel
- [ ] Backend starts with production host/port binding
- [ ] Frontend builds successfully in hosted environment

### Environment readiness

- [ ] Production Neon database created
- [ ] Staging Neon database or branch created
- [ ] Production backend service created
- [ ] Staging backend service created
- [ ] Production frontend project created
- [ ] Staging or preview frontend deployment path confirmed

### Operational readiness

- [ ] Health check endpoint verified: `/health`
- [ ] Database health check endpoint verified: `/health/db`
- [ ] `/health/db` returns `200` when the deployed database is reachable
- [ ] `/health/db` returns `503` when the database is unavailable or misconfigured
- [ ] Smoke test key frontend flows after deploy:
  - search
  - graph
  - entity detail
- [ ] Error logs are visible in hosting platform dashboards
- [ ] Secrets are stored in platform env var management, not committed files

### Process readiness

- [ ] Staging deploy process documented and tested
- [ ] Production deploy process documented before first release
- [ ] Rollback owner and rollback steps agreed on

## Recommended First Rollout Order

1. Provision Neon staging and production databases.
2. Deploy backend staging service and verify `/health` and `/health/db`.
3. Configure Vercel staging or preview frontend against staging backend.
4. Validate end-to-end flows in staging.
5. Add production-ready CORS configuration in code.
6. Deploy backend production service.
7. Deploy frontend production project with production API base URL.

## Backend Container Build And Run

The backend can be packaged as a standalone Docker image without bundling
Postgres. Production Postgres remains an external managed service.

### Build the image

From the repository root:

```bash
docker build -t hoyoverse-graph-api .
```

### Required runtime environment variables

- `DATABASE_URL`
- `ALLOWED_ORIGINS`
- `PORT` when provided by the hosting platform

### Run locally against the existing Docker Compose Postgres

Because the local Postgres container publishes port `5432` on the host, the
backend container should connect to the host machine, not to `localhost`
inside the container.

On macOS and Docker Desktop, use `host.docker.internal`:

```bash
docker run --rm \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://hoyo:hoyo_dev_password@host.docker.internal:5432/hoyoverse_graph" \
  -e ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000" \
  hoyoverse-graph-api
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
```

If you later run this on Linux, you may need to provide an explicit host-gateway
mapping or use a Docker network-aware Postgres hostname instead of
`host.docker.internal`.

## Frontend Container Build And Run

The frontend can also be packaged as a standalone Docker image for portability
and production-like local testing. The planned production deployment target
remains Vercel, so this Dockerfile is optional for the hosted deployment path.

### Build the image

From the repository root:

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  -t hoyoverse-graph-frontend \
  ./frontend
```

### Run the image locally

```bash
docker run --rm -p 3000:3000 hoyoverse-graph-frontend
```

Then open:

```text
http://localhost:3000
```

### Runtime notes

- The container listens on `0.0.0.0`.
- `PORT` defaults to `3000` when not supplied.
- For local frontend-to-backend communication in the browser, build the image
  with a browser-accessible API URL such as `http://localhost:8000` or
  `http://127.0.0.1:8000`.
- Vercel does not require this Dockerfile for the planned production deployment.

## Future Improvements

- Add environment-aware CORS configuration
- Add deployment runbooks for staging and production
- Add CI/CD workflows once manual deployment flow is stable
- Add Dockerfiles later if platform needs or local parity make them useful
