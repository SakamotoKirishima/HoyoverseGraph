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
- The initial GitHub Actions deployment workflow is wired for Render deploy
  hooks to keep the first rollout simple and explicit.

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
  - optional source of truth for `DATABASE_URL_DIRECT` when you want a separate
    direct/admin connection for schema bootstrap or other manual operations
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
DATABASE_URL_DIRECT=postgresql://<user>:<password>@<direct-host>/<database>?sslmode=require
ALLOWED_ORIGINS=https://<production-frontend-domain>
PORT=8000

# Frontend
NEXT_PUBLIC_API_BASE_URL=https://<production-backend-domain>
```

## Database Deployment (Neon Postgres)

The application already connects through a standard `DATABASE_URL` using
`psycopg.connect(...)`, so it is compatible with Neon-style PostgreSQL URLs.
Local Docker Postgres continues to work with the current non-SSL local URL, and
Neon production or staging URLs should keep `sslmode=require`.

### Pooled vs direct connection strings

- `DATABASE_URL`
  - Use the Neon pooled connection string for normal backend runtime traffic
  - Configure this in Render or Railway
  - Neon pooled hostnames typically include `-pooler`
- `DATABASE_URL_DIRECT`
  - Optional
  - Keep this for manual schema bootstrap, one-off admin work, or other tasks
    where you explicitly want a direct connection
  - This is documented as a separate env var, but it is not used by runtime
    application code today
  - Use the Neon direct/unpooled hostname here, not a `-pooler` hostname

### Staging and production separation

- Create a production Neon database or production branch
- Create a separate staging Neon database or staging branch
- Store separate `DATABASE_URL` values for staging and production
- Store separate `DATABASE_URL_DIRECT` values for staging and production if you
  choose to keep direct/admin URLs
- Never reuse production database credentials in staging

### Schema bootstrap for Neon

Local Docker Postgres applies [db/schema.sql](../db/schema.sql) automatically
through `docker-entrypoint-initdb.d`, but Neon will not do that for you.

Current status:

- `db/schema.sql` appears safe to rerun because it uses `CREATE TABLE IF NOT
  EXISTS`, `CREATE INDEX IF NOT EXISTS`, and guarded `DO $$ ... $$` blocks for
  foreign-key additions.
- No migration framework is currently in place.

Manual bootstrap command for an empty Neon database:

```bash
psql "$DATABASE_URL_DIRECT" -f db/schema.sql
```

If you do not keep a separate direct URL, you can use:

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

### Manual ingestion against Neon

Do not seed staging or production automatically during application startup.
Run ingestion manually with the appropriate environment variables for the target
environment.

Example sequence:

```bash
export DATABASE_URL="<staging-or-production-neon-url>"
python -m ingestion.ingest_entities --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_sources --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_claims --workbook docs/hoyoverse_ontology_v1.xlsm
```

Practical ingestion dependency order:

1. entities
2. sources
3. source assets
4. claims

Notes:

- `python -m ingestion.ingest_sources` loads both `sources` and `source_assets`
  in a single step.
- Claims must be loaded last because they can reference entities, sources, and
  source assets.

Use the staging `DATABASE_URL` for staging ingestion and the production
`DATABASE_URL` for production ingestion. Never point staging ingestion at the
production database.

### Neon setup checklist

1. In the Neon dashboard, create or identify the production project/database.
2. Create a separate staging database or branch.
3. Copy the pooled connection string for each environment into:
   - Render or Railway `DATABASE_URL`
4. Optionally copy the direct connection string for each environment into:
   - local secure admin shell as `DATABASE_URL_DIRECT`
   - or hosted secret storage if your team needs it there
5. Apply the schema manually with `psql`.
6. Run ingestion manually for the target environment.
7. Verify the backend database check:

```bash
curl http://127.0.0.1:8000/health/db
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

## GitHub Actions Deployment Workflow

The repository includes a manual deployment workflow:

- workflow: `.github/workflows/deploy.yml`
- trigger: `workflow_dispatch`
- environments:
  - `staging`
  - `production`

This first version is intentionally staging-first and conservative:

- it does not auto-deploy production on push
- it does not apply schema changes automatically
- it does not run ingestion automatically
- it validates backend and frontend checks before any deploy step runs
- it keeps frontend deployment Git-managed in Vercel for now
- it triggers backend deployment through a Render deploy hook

### What the workflow does

1. Runs backend validation:
   - `ruff check .`
   - `pytest`
2. Runs frontend validation:
   - `npm run lint`
   - `npm run build`
   - `npm test -- --run`
3. Triggers the backend deployment using the environment-specific Render deploy
   hook.
4. Performs smoke checks against:
   - `GET <BACKEND_URL>/health`
   - `GET <BACKEND_URL>/health/db`
   - `GET <FRONTEND_URL>`

The smoke checks use a short retry loop so the workflow can wait for the hosted
services to become healthy after a deployment trigger.

### Manual trigger steps

1. Open the GitHub repository.
2. Go to **Actions**.
3. Open the **Deploy** workflow.
4. Click **Run workflow**.
5. Choose `staging` or `production`.
6. Start the workflow.

Recommended order:

1. Deploy `staging`
2. Verify staging behavior
3. Deploy `production`

### Required GitHub Environments

Create these GitHub Environments:

- `staging`
- `production`

The deploy job uses:

```yaml
environment: ${{ inputs.environment }}
```

That allows environment-specific secrets, variables, reviewers, and protection
rules to be added later without rewriting the workflow.

### Required GitHub Environment configuration

For each GitHub Environment, configure:

Environment variables:

- `BACKEND_URL`
  - example staging value: `https://staging-api.example.com`
  - example production value: `https://api.example.com`
- `FRONTEND_URL`
  - example staging value: `https://staging-frontend.example.com`
  - example production value: `https://your-vercel-app.vercel.app`

Environment secrets:

- `RENDER_DEPLOY_HOOK`
  - Render deploy hook URL for that environment's backend service

Optional Vercel secrets are not required for the current workflow because the
frontend remains Git-managed by Vercel:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

If the team later decides to deploy Vercel explicitly from GitHub Actions,
those values can be added then.

### Deployment order

1. Ensure required checks are green on the branch you intend to deploy.
2. Ensure environment-specific secrets and variables are configured.
3. Trigger the workflow for `staging`.
4. Wait for smoke checks to pass.
5. Verify key user flows in staging.
6. Trigger the workflow for `production`.
7. Verify smoke checks and hosted application behavior.

### Rollback

Rollback is initially handled through provider deployment history rather than
through automated GitHub Actions rollback steps.

- Vercel rollback: use Vercel deployment history
- Render rollback: use Render deployment history or redeploy a known-good
  version

This keeps the first deployment workflow simple while still giving operators a
clear recovery path.

## Staging Environment Setup

This section is the recommended first hosted environment to create. Set up
staging fully before touching production resources.

### 1. Create the GitHub Environment

Create a GitHub Environment named:

- `staging`

Configure the following values for that environment.

Environment variables:

- `BACKEND_URL`
  - example: `https://staging-api.example.com`
- `FRONTEND_URL`
  - example: `https://staging-hoyoverse-graph.vercel.app`

Environment secrets:

- `RENDER_DEPLOY_HOOK`
  - Render deploy hook URL for the staging backend service

Notes:

- `DATABASE_URL` does not need to live in the GitHub Environment for the
  current workflow because the workflow does not run migrations or seed data.
- `DATABASE_URL` must still be configured in the staging backend host itself.
- Vercel CLI credentials are not required for the current workflow because the
  frontend remains Git-managed by Vercel.

### 2. Create the Neon staging database

In Neon:

1. Open the Neon dashboard.
2. Create a dedicated staging database or staging branch.
3. Copy the pooled connection string for application traffic.
4. Optionally copy the direct connection string for manual admin work.

Recommended variable mapping:

- staging backend host `DATABASE_URL`
  - Neon pooled connection string
- local secure shell `DATABASE_URL_DIRECT`
  - Neon direct connection string for manual schema/bootstrap work

Important:

- Keep the pooled application URL and the direct admin URL distinct.
- Do not put a Neon `-pooler` hostname into `DATABASE_URL_DIRECT`.

Do not reuse production credentials or connect staging services to the
production database.

### 3. Apply schema to staging

Bootstrap the staging schema manually:

```bash
export DATABASE_URL_DIRECT="<staging-neon-direct-url>"
psql "$DATABASE_URL_DIRECT" -f db/schema.sql
```

If you are not using a separate direct connection string:

```bash
export DATABASE_URL="<staging-neon-pooled-url>"
psql "$DATABASE_URL" -f db/schema.sql
```

### 4. Load seed data into staging

Run ingestion manually against staging after the schema is in place:

```bash
export DATABASE_URL="<staging-neon-pooled-url>"
python -m ingestion.ingest_entities --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_sources --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_claims --workbook docs/hoyoverse_ontology_v1.xlsm
```

Do not run ingestion automatically on every deploy.

### 5. Create the staging backend service

Create a separate staging backend service in Render.

Use the production startup command:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Configure these runtime environment variables in the staging backend host:

- `DATABASE_URL=<staging Neon pooled URL>`
- `ALLOWED_ORIGINS=<staging frontend URL>`

Important:

- `ALLOWED_ORIGINS` should contain only staging or preview frontend URLs.
- Do not include the production frontend origin unless there is a deliberate
  reason to do so.

Health check path:

- `/health`

Validate after deployment:

```bash
curl https://<staging-backend-domain>/health
curl https://<staging-backend-domain>/health/db
```

### 6. Create the staging frontend deployment

Create a Vercel staging or preview deployment for the frontend.

Configure:

- `NEXT_PUBLIC_API_BASE_URL=<staging backend URL>`

Because `NEXT_PUBLIC_API_BASE_URL` is a build-time public value, staging builds
must use the staging backend URL. Do not point staging frontend builds at the
production backend.

If you change `NEXT_PUBLIC_API_BASE_URL`, you must rebuild and redeploy the
frontend for the updated backend URL to be embedded into the client bundle.

### 7. Manually run the staging deployment workflow

After staging backend/frontend resources and GitHub Environment values are in
place:

1. Open **Actions** in GitHub.
2. Open the **Deploy** workflow.
3. Click **Run workflow**.
4. Select `staging`.
5. Start the workflow.

The workflow will:

1. run backend and frontend validation
2. trigger the staging backend deploy through Render
3. check:
   - `GET <BACKEND_URL>/health`
   - `GET <BACKEND_URL>/health/db`
   - `GET <FRONTEND_URL>`

### 8. Staging smoke validation

After the workflow succeeds, verify:

- Search page loads and returns results
- Graph page loads
- Entity detail page loads
- Backend `/health` passes
- Backend `/health/db` passes

Suggested manual checks:

```bash
curl https://<staging-backend-domain>/health
curl https://<staging-backend-domain>/health/db
```

Then open the staging frontend and test:

- `/search?q=kaslana`
- `/graph?seed_entity_id=ENT-0804&depth=1`
- `/entities/ENT-0804`

### Staging checklist

- [ ] staging GitHub Environment created
- [ ] staging `BACKEND_URL` configured
- [ ] staging `FRONTEND_URL` configured
- [ ] staging `RENDER_DEPLOY_HOOK` configured
- [ ] staging Neon DB created
- [ ] schema applied
- [ ] seed data loaded
- [ ] staging backend created
- [ ] staging frontend created
- [ ] staging env vars configured
- [ ] staging CORS configured
- [ ] `/health` passes
- [ ] `/health/db` passes
- [ ] Search smoke test passes
- [ ] Graph smoke test passes
- [ ] Entity detail smoke test passes

## Production Environment Setup

Production should stay fully isolated from staging. Do not reuse staging
database URLs, deploy hooks, frontend URLs, or secrets in the production
environment.

### 1. Create the GitHub Environment

Create a GitHub Environment named:

- `production`

Configure the following values for that environment.

Environment variables:

- `BACKEND_URL`
  - example: `https://api.example.com`
- `FRONTEND_URL`
  - example: `https://your-vercel-app.vercel.app`

Environment secrets:

- `RENDER_DEPLOY_HOOK`
  - Render deploy hook URL for the production backend service

Optional Vercel secrets if the team later decides to deploy Vercel directly
from GitHub Actions:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

If GitHub Environment protection rules are available for this repository,
enable manual approval for the `production` environment before deploy jobs can
run.

Notes:

- `DATABASE_URL` does not need to live in the GitHub Environment for the
  current workflow because the workflow does not run schema bootstrap or data
  ingestion.
- `DATABASE_URL` must still be configured in the production backend host.
- Never commit or echo production secrets.

### 2. Create the Neon production database

In Neon:

1. Open the Neon dashboard.
2. Create or identify a dedicated production database or production branch.
3. Confirm that production remains separate from staging.
4. Copy the pooled connection string for application traffic.
5. Optionally copy the direct connection string for manual schema/bootstrap
   operations.

Recommended variable mapping:

- production backend host `DATABASE_URL`
  - Neon pooled connection string
- local secure shell `DATABASE_URL_DIRECT`
  - Neon direct connection string for manual schema/bootstrap work

Production must never reuse the staging `DATABASE_URL`.

### 3. Bootstrap the production schema intentionally

Do not apply schema automatically at app startup. Bootstrap production
intentionally and only after confirming the target database is correct.

Preferred command:

```bash
export DATABASE_URL_DIRECT="<production-neon-direct-url>"
psql "$DATABASE_URL_DIRECT" -f db/schema.sql
```

Fallback if you do not keep a separate direct connection string:

```bash
export DATABASE_URL="<production-neon-pooled-url>"
psql "$DATABASE_URL" -f db/schema.sql
```

Current status:

- `db/schema.sql` appears safely rerunnable because it uses `CREATE TABLE IF NOT
  EXISTS`, `CREATE INDEX IF NOT EXISTS`, and guarded constraint creation blocks.
- Even so, schema bootstrap should remain a deliberate operator action in
  production.

### 4. Load production seed data intentionally

Run production ingestion manually only after:

1. the same release has passed staging smoke validation
2. the target production database has been verified
3. the input workbook/data has been reviewed

Example command sequence:

```bash
export DATABASE_URL="<production-neon-pooled-url>"
python -m ingestion.ingest_entities --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_sources --workbook docs/hoyoverse_ontology_v1.xlsm
python -m ingestion.ingest_claims --workbook docs/hoyoverse_ontology_v1.xlsm
```

Practical ingestion dependency order remains:

1. entities
2. sources
3. source assets
4. claims

Warnings:

- Do not run ingestion automatically during deployment.
- Verify the same workbook and ingestion flow against staging first.
- Do not point staging ingestion at production, or production ingestion at
  staging, by mistake.

### 5. Create the production backend service

Create a separate production backend service in Render.

Use the production startup command:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Configure these runtime environment variables in the production backend host:

- `DATABASE_URL=<production Neon pooled connection string>`
- `ALLOWED_ORIGINS=<production frontend origin>`

Health check path:

- `/health`

Validate after deployment:

```bash
curl https://<production-backend-domain>/health
curl https://<production-backend-domain>/health/db
```

Production backend must not use staging DB credentials.

### 6. Create the production frontend deployment

Use the production Vercel project or production deployment target for the
frontend.

Configure:

- `NEXT_PUBLIC_API_BASE_URL=<production backend URL>`

Important:

- `NEXT_PUBLIC_API_BASE_URL` is a public build-time value.
- The production frontend must use the production backend URL.
- Do not point the production frontend at the staging backend.
- Changing `NEXT_PUBLIC_API_BASE_URL` requires a frontend rebuild/redeploy.

### 7. Configure production CORS

Production `ALLOWED_ORIGINS` should contain only approved production frontend
origins.

Example:

```bash
ALLOWED_ORIGINS=https://<production-domain>
```

Do not use `*`, and do not include staging URLs unless there is an explicit and
reviewed need.

### 8. Run the production deployment workflow manually

Production deployment remains manual for now.

To run it:

1. Open **Actions** in GitHub.
2. Open the **Deploy** workflow.
3. Click **Run workflow**.
4. Select `production`.
5. Start the workflow.

Recommended preconditions:

- required CI checks are green
- staging smoke tests passed for the same release
- production environment secrets and variables are already configured
- reviewers or approvers have signed off if environment protection is enabled

### 9. Pre-deployment checks

Before production deployment, verify:

Backend:

- `pytest`
- `ruff check .`

Frontend:

- `npm run build`
- `npm run lint`
- `npm test`

Also confirm the corresponding staging deployment has already passed smoke
validation for the same release candidate.

### 10. Post-deployment validation

After the production deployment completes, verify:

Backend:

- `GET /health`
- `GET /health/db`

Frontend:

- homepage loads
- Search page works
- Graph page works
- Entity Detail page works

Suggested manual checks:

```bash
curl https://<production-backend-domain>/health
curl https://<production-backend-domain>/health/db
```

Then open the production frontend and test:

- `/`
- `/search?q=kaslana`
- `/graph?seed_entity_id=ENT-0804&depth=1`
- `/entities/ENT-0804`

Verify that frontend requests are reaching the production backend successfully.

### 11. Rollback

Initial rollback strategy:

- frontend: redeploy the previous known-good Vercel deployment
- backend: redeploy the previous known-good Render deployment
- database changes are not automatically rolled back

Important:

- destructive or data-changing DB operations require a separate migration,
  backup, and recovery strategy
- this workflow does not attempt DB rollback

## Staging Validation Findings

- Missing `/health/db` endpoint
  - Fixed
  - The endpoint now exists, returns `200` when the database is reachable, and
    returns `503` when it is unavailable. Coverage lives in
    `tests/test_health_api.py`.
- Neon staging had schema but no ingested seed data
  - Fixed
  - Schema bootstrap and ingestion are now documented as separate required
    manual steps. Staging must load data explicitly after schema creation.
- `DATABASE_URL_DIRECT` was accidentally set to a pooled Neon URL
  - Fixed in documentation
  - This document now distinguishes pooled runtime URLs from direct admin URLs
    and explicitly warns against using `-pooler` hostnames for
    `DATABASE_URL_DIRECT`.
- Vercel staging initially failed to fetch from Render
  - Fixed/documented
  - Staging docs now call out that `NEXT_PUBLIC_API_BASE_URL` must point to the
    Render backend, `ALLOWED_ORIGINS` must allow the Vercel staging origin, and
    changing `NEXT_PUBLIC_API_BASE_URL` requires a frontend rebuild/redeploy.
- Frontend test infrastructure and smoke tests were missing
  - Fixed
  - Vitest, React Testing Library, smoke tests for Search/Graph/Entity Detail,
    and the `frontend-test` workflow are now in place.
- Clean-clone setup exposed missing dependency/setup assumptions
  - Fixed/documented
  - README now includes Python virtualenv setup, runtime and dev dependency
    installation, local env file creation, Docker Postgres startup, frontend
    `npm ci`, and startup commands from a fresh clone.

Follow-up remaining:

- Branch protection itself must be updated in GitHub settings if the hosted repo
  has not already been changed to require `frontend-test`.

### Production readiness checklist

- [ ] production Neon DB created
- [ ] production DB credentials stored securely
- [ ] schema applied
- [ ] seed data validated and loaded
- [ ] production backend service created
- [ ] production frontend project created
- [ ] production environment variables configured
- [ ] production CORS restricted correctly
- [ ] GitHub production environment configured
- [ ] required CI checks pass
- [ ] staging smoke tests pass
- [ ] `/health` passes
- [ ] `/health/db` passes
- [ ] Search smoke test passes
- [ ] Graph smoke test passes
- [ ] Entity Detail smoke test passes
- [ ] rollback procedure documented

## Recommended First Rollout Order

1. Provision Neon staging and production databases.
2. Deploy backend staging service and verify `/health` and `/health/db`.
3. Configure Vercel staging or preview frontend against staging backend.
4. Validate end-to-end flows in staging.
5. Configure production `ALLOWED_ORIGINS` for the deployed frontend domain.
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
