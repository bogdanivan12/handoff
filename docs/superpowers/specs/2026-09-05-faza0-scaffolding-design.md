# Phase 0 — Scaffolding — Design

Sub-project of [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Phase 0. First vertical
slice of the Handoff platform: base infrastructure (backend + frontend +
docker-compose), no business logic yet. Goal: `docker-compose up` starts
everything, `/health` confirms real DB connectivity.

## Context

Repo was empty at the time of this spec (only `README.md`). Tech stack fixed
in `HANDOFF_SPEC.md` §2: Python/FastAPI, SQLAlchemy 2.0 async, Alembic,
Postgres 15+ with `pgvector`, React/TS/Vite/Tailwind/shadcn, docker-compose
locally, deploy target k3s (homelab, Proxmox).

Important decision (differs from the implicit assumption in the general
spec): **Postgres does not run locally in docker-compose.** The user already
has a Postgres instance on their k3s homelab; the backend connects to it
directly, both for local dev and for deploy. `pgvector` is assumed to
already be installed there — not this phase's responsibility.

## Layout

```
/backend   FastAPI + SQLAlchemy 2.0 async + Alembic
/frontend  Vite + React + TS + Tailwind + shadcn/ui
/infra     docker-compose (backend + frontend; no Postgres)
```

## Backend

- Python 3.12, `uv` as package manager (lockfile, fast Docker layer cache)
- `asyncpg` driver, SQLAlchemy 2.0 async engine
- `pydantic-settings` reads `DATABASE_URL` from the environment (local
  `.env`, not committed; `.env.example` with a placeholder)
- Alembic configured for async (adapted env.py), **empty baseline** migration
  — creates no table. The initial migration's only purpose is to confirm
  Alembic can talk to the DB. Tables from `schema.sql` + the new fields from
  the spec come incrementally, one slice per phase (Phase 1 = Product/
  Initiative/Epic/Feature, etc.) — not all at once.
- `GET /health` → `{"status": "ok", "db": "connected"}` or
  `{"status": "error", "db": "error"}` (HTTP 200 vs 503). Runs `SELECT 1` on
  the connection on every call (not cached) so it reflects the real state.
- CORS middleware active, allowed origin = `http://localhost:5173` (Vite dev
  server), configurable via env for other origins later.

## Frontend

- Vite + React + TypeScript, Tailwind CSS, shadcn/ui initialized (base
  components installed: `button`, `card` — enough for the test screen)
- npm as package manager
- Test screen at `/`: on load, calls `GET {VITE_API_URL}/health`, shows a
  card with visual status (green = ok, red = error/unreachable)
- `VITE_API_URL` configurable via env (`.env.example` with default
  `http://localhost:8000`)

## Infra (docker-compose)

- `infra/docker-compose.yml`, two services:
  - `backend`: built from `/backend/Dockerfile`, uvicorn with `--reload`,
    source code volume mount for hot-reload, `env_file: ../backend/.env`
  - `frontend`: built from `/frontend/Dockerfile`, `npm run dev -- --host`,
    source code volume mount, `env_file: ../frontend/.env`
- No `postgres` service — connection to the homelab happens through
  `DATABASE_URL` in the backend's `.env` (the user's LAN/VPN network must
  allow access; this is the user's responsibility, not scripted here)
- `docker-compose up` from `/infra` starts both services

## Testing

- Backend: pytest, one test for `/health` with the DB connection mocked
  (does not depend on live access to the homelab — the test checks both
  branches: connection ok and connection raising an exception)
- Frontend: manual visual check of the test screen (no automated suite in
  this phase — YAGNI, there's no logic to test yet)

## What we are NOT building in Phase 0

- No business tables (Product, Feature, Task, etc.) — comes per phase,
  starting with Phase 1
- No k3s deploy manifest (left for a later phase / separate decision)
- Authentication (explicitly excluded from the MVP per §7 of the general
  spec)

## Open risks / assumptions

- The homelab Postgres already has the `pgvector` extension installed — not
  verified, not installed here
- The local dev environment can reach the homelab k3s over the network
  (LAN/VPN) — if not, `/health` will report `db: error`, which is the
  correct signaling behavior, not a bug to fix in this phase
