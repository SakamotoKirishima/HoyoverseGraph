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

Recommended example:

```bash
DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
```

Notes:

- The backend currently reads `DATABASE_URL` directly.
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

## Current Deployment Gaps To Address Before Go-Live

These are important findings from the current codebase:

- Backend CORS is currently hardcoded for:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- A deployed frontend on Vercel will not be allowed until backend CORS is made
  environment-aware.
- This should be treated as a deployment readiness blocker for production.

Recommended future configuration change:

- introduce an env var such as `ALLOWED_ORIGINS`
- configure it separately for staging and production

This document does not implement that change; it only records the required
follow-up.

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

### Recommended separation

- Do not share the same database between staging and production.
- Do not point Vercel preview deployments at production data by default.
- Keep staging and production secrets separate across all platforms.

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
2. Deploy backend staging service and verify `/health`.
3. Configure Vercel staging or preview frontend against staging backend.
4. Validate end-to-end flows in staging.
5. Add production-ready CORS configuration in code.
6. Deploy backend production service.
7. Deploy frontend production project with production API base URL.

## Future Improvements

- Add environment-aware CORS configuration
- Add deployment runbooks for staging and production
- Add CI/CD workflows once manual deployment flow is stable
- Add Dockerfiles later if platform needs or local parity make them useful
