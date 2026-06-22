# AGENTS.md

This document captures coding and testing standards for AI agents and contributors working in this repository.

## Development Commands

Standard test command:

```bash
pytest
```

Standard lint command:

```bash
ruff check .
```

Standard format command:

```bash
ruff format .
```

Standard pre-commit command:

```bash
pre-commit run --all-files
```

## Frontend Commands

- Always run frontend commands from `frontend/`.
- Use `npm`, not `yarn`.
- Before opening a PR for frontend changes, run:

```bash
npm run build
npm run lint
npm test
```

- Build failures must be fixed before merge.
- Frontend CI checks:
  - `frontend-build`
  - `frontend-lint`
  - `frontend-test` (informational for now)

## Frontend Testing

- Frontend smoke tests will use `Vitest`, `React Testing Library`, and `jsdom`.
- These tests will cover lightweight page and component behavior for the Next.js frontend.
- Frontend tests currently run in CI but are not required for merge.
- Promote `frontend-test` to a required merge check after 3-5 consecutive PRs pass without flaky failures.
- Standard frontend test command:

```bash
npm test
```

## Merge Policy

- Required checks today:
  - `pytest`
  - `ruff`
  - `frontend-build`
  - `frontend-lint`
- Future required check:
  - `frontend-test`
- Do not change branch protection or merge expectations casually; document policy updates alongside CI changes.

## Testing Standards

- All new features should include unit tests.
- Bug fixes should include regression tests when practical.
- CI blocks merges when `ruff check .` or `pytest` fail.
- Tests should avoid requiring a live Postgres instance unless they are explicitly marked as integration tests.
- For API unit tests, prefer monkeypatching or repository-level fakes over real database access.
- API tests should stay focused on status codes, response shape, validation behavior, and conflict handling.
- Helper tests should stay focused on pure validation and normalization logic.

## Branching Standards

### Branch naming

- Work should happen on a branch, not directly on `main`.
- Use one of these branch prefixes:
  - `feature/<short-description>`
  - `fix/<short-description>`
  - `chore/<short-description>`
  - `docs/<short-description>`
  - `test/<short-description>`
- Keep branches scoped to one feature, fix, chore, docs change, or test task.
- Example branch names:
  - `feature/search-page`
  - `feature/graph-page`
  - `chore/nextjs-upgrade`
  - `fix/entity-detail-links`
  - `test/frontend-smoke-tests`

### PR workflow

- Open a pull request into `main` for every change.
- Keep each PR scoped to one feature, fix, chore, docs update, or test task.
- Use the repository PR template.
- Verify CI before merge.
- Delete merged branches after merge.
- Rebase or update from `main` when a branch becomes stale.

### Commit style

- Use short imperative commit messages.
- Good examples:
  - `Add graph endpoint`
  - `Fix source asset validation`
  - `Document frontend commands`
  - `Upgrade Next.js`
- Avoid vague commits like `updates` or `fix stuff`.
- Avoid unrelated changes in the same commit.

### Required checks

- Current required checks before merge:
  - `pytest`
  - `ruff`
  - `frontend-build`
  - `frontend-lint`
- Future required check:
  - `frontend-test`

### Frontend tests

- `frontend-test` runs in CI but is informational for now.
- Promote `frontend-test` to required after 3-5 consecutive PRs pass without flaky failures.

### Merge readiness

- Required checks must pass.
- PRs should have a clear description.
- Testing steps should be documented.
- No unrelated changes should be included.
- Secrets and `.env` files must not be committed.

## Coding Standards

- Keep changes small and focused.
- Prefer typed Python where practical.
- Keep route handlers thin.
- Put shared validation and normalization logic in helper modules.
- Use parameterized SQL only.
- Do not log secrets or `DATABASE_URL`.
- Preserve existing API response shapes unless the task explicitly changes them.
- Add or update unit tests for new behavior.
- Avoid broad rewrites unless explicitly requested.
- Do not introduce live Postgres requirements into unit tests unless they are marked as integration tests.

## General Guidance

- Keep changes scoped to the task at hand.
- Update documentation when behavior or developer workflow changes.
- Prefer small, readable tests over broad integration-heavy coverage when unit coverage is sufficient.
