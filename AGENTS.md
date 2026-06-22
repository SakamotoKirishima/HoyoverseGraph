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

## Branch Management

- Work should happen on feature branches, not directly on `main`.
- Preferred branch naming:
  - `feature/<short-description>`
  - `fix/<short-description>`
  - `docs/<short-description>`
  - `chore/<short-description>`
- Keep each branch scoped to one task.
- Open a pull request into `main` for review and CI.
- Do not merge if `ruff check .` or `pytest` checks fail.
- Rebase or update from `main` when a branch becomes stale.
- Delete merged branches after the pull request is merged.

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
