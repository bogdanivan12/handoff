# Handoff

Product & project management platform, product-centric, built for the era of AI-assisted development. See `HANDOFF_SPEC.md` for the full project spec.

## Running locally

This project connects to an external Postgres instance (no local Postgres container) — see `docs/superpowers/specs/2026-09-05-phase0-scaffolding-design.md` for why.

1. Copy the env templates and fill in real values:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
   Edit `backend/.env` with a real `DATABASE_URL` pointing at a reachable Postgres instance.

2. Start both services:
   ```bash
   docker-compose -f infra/docker-compose.yml up --build
   ```
   Frontend: http://localhost:5173 — Backend: http://localhost:8000/health

**Gotcha:** if you've already run `uv sync` in `backend/` or `npm install` in `frontend/` directly on your host (e.g. to run tests locally), delete the resulting `backend/.venv` / `frontend/node_modules` before the first `docker-compose up --build` — a stale host copy can conflict with the container's own. See the comments in `infra/docker-compose.yml` for details.

## Project structure

- `backend/` — FastAPI + SQLAlchemy 2.0 async + Alembic
- `frontend/` — Vite + React + TypeScript + Tailwind + shadcn/ui
- `infra/` — docker-compose for local development
