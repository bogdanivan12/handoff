# Phase 0 Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Handoff repo skeleton — a FastAPI backend, a Vite/React/TS frontend, and docker-compose wiring — so `docker-compose up` starts both services and a `/health` endpoint proves the backend can really reach Postgres.

**Architecture:** Three independent top-level directories (`/backend`, `/frontend`, `/infra`). Backend is a plain FastAPI app with an async SQLAlchemy engine and an Alembic baseline (no tables yet — those come per future phase). Frontend is a Vite/React/TS app with Tailwind + shadcn/ui and a single test screen that calls the backend's `/health`. No Postgres container: the backend connects directly to the user's existing homelab Postgres via `DATABASE_URL`.

**Tech Stack:** Python 3.12, `uv`, FastAPI, SQLAlchemy 2.0 async, `asyncpg`, Alembic, `pydantic-settings`, pytest, httpx; Node/npm, Vite, React, TypeScript, Tailwind CSS v4, shadcn/ui; Docker + docker-compose.

**Spec:** [docs/superpowers/specs/2026-09-05-faza0-scaffolding-design.md](../specs/2026-09-05-faza0-scaffolding-design.md)

## Global Constraints

- Python >=3.12, package manager `uv` (backend)
- SQLAlchemy 2.0 async (`sqlalchemy[asyncio]`) with `asyncpg` driver — no sync engine
- Postgres 15+ with `pgvector` — assumed already installed on the homelab instance; not verified or installed by this plan
- No local Postgres container. Backend always connects via `DATABASE_URL` (env var) to the homelab k3s Postgres, both in local dev and in docker-compose
- Alembic migration in this phase is an **empty baseline only** — no business tables. Tables are added incrementally in later phases
- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui, npm as package manager
- No authentication (explicitly out of scope for the MVP)
- All repo content (code, comments, docs, commit messages) in English

---

### Task 1: Backend Project Scaffolding + Settings Config

**Files:**
- Create: `.gitignore` (repo root)
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.config.settings` — a `Settings` instance (pydantic `BaseSettings`) with fields `database_url: str` and `cors_origins: list[str]` (default `["http://localhost:5173"]`). Task 2 imports `settings` for the DB engine and CORS middleware.

- [ ] **Step 1: Create root `.gitignore`**

```
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/

# Node
node_modules/
dist/

# Env
.env

# OS
.DS_Store
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "handoff-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic-settings>=2.6",
]

[tool.uv]
package = false

[dependency-groups]
dev = [
    "pytest>=8.3",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Install dependencies**

Run: `cd backend && uv sync`
Expected: exits 0, creates `backend/.venv/` and `backend/uv.lock`.

- [ ] **Step 4: Create empty package markers**

Create `backend/app/__init__.py` (empty file) and `backend/tests/__init__.py` (empty file).

- [ ] **Step 5: Create `backend/tests/conftest.py`**

```python
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
```

- [ ] **Step 6: Write the failing test**

Create `backend/tests/test_config.py`:

```python
from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/handoff"
    )
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/handoff"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v` (from `backend/`)
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 8: Write minimal implementation**

Create `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
```

- [ ] **Step 9: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v` (from `backend/`)
Expected: `1 passed`

- [ ] **Step 10: Commit**

```bash
git add .gitignore backend/pyproject.toml backend/uv.lock backend/app/__init__.py backend/app/config.py backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat(backend): add project scaffolding and settings config"
```

---

### Task 2: DB Session + `/health` Endpoint

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`
- Create: `backend/.env.example`
- Create: `backend/Dockerfile`

**Interfaces:**
- Consumes: `app.config.settings` (Task 1) — `.database_url`, `.cors_origins`
- Produces: `app.db.get_db` — an async generator FastAPI dependency yielding an `AsyncSession`. `app.main.app` — the FastAPI instance, entrypoint used by uvicorn (`app.main:app`) in Task 5's docker-compose.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_health.py`:

```python
from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


class _FakeSessionOk:
    async def execute(self, *args, **kwargs):
        return None


class _FakeSessionError:
    async def execute(self, *args, **kwargs):
        raise ConnectionError("db unreachable")


async def _override_ok() -> AsyncGenerator[_FakeSessionOk, None]:
    yield _FakeSessionOk()


async def _override_error() -> AsyncGenerator[_FakeSessionError, None]:
    yield _FakeSessionError()


def test_health_returns_ok_when_db_reachable():
    app.dependency_overrides[get_db] = _override_ok
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "connected"}


def test_health_returns_error_when_db_unreachable():
    app.dependency_overrides[get_db] = _override_error
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_health.py -v` (from `backend/`)
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Implement the DB session**

Create `backend/app/db.py`:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

- [ ] **Step 4: Implement the health router**

Create `backend/app/routers/__init__.py` (empty file).

Create `backend/app/routers/health.py`:

```python
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter()


@router.get("/health")
async def health(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "db": "error"}
    return {"status": "ok", "db": "connected"}
```

- [ ] **Step 5: Implement the FastAPI app**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router

app = FastAPI(title="Handoff API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_health.py -v` (from `backend/`)
Expected: `2 passed`

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `3 passed`

- [ ] **Step 8: Create the env template**

Create `backend/.env.example`:

```
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/handoff
```

- [ ] **Step 9: Create the Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/db.py backend/app/routers backend/app/main.py backend/tests/test_health.py backend/.env.example backend/Dockerfile
git commit -m "feat(backend): add async DB session and /health endpoint"
```

---

### Task 3: Alembic Baseline Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_baseline.py`

**Interfaces:**
- Consumes: `app.config.settings.database_url` (Task 1)
- Produces: nothing consumed by later tasks in this plan (Alembic CLI usage only; future phases add revisions with `down_revision = "0001"`)

- [ ] **Step 1: Generate the async Alembic scaffold**

Run: `cd backend && uv run alembic init -t async alembic`
Expected: creates `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/`.

- [ ] **Step 2: Point Alembic at our settings instead of a hardcoded URL**

In `backend/alembic.ini`, find the line:

```
sqlalchemy.url = driver://user:pass@localhost/dbname
```

Replace it with:

```
sqlalchemy.url =
```

(left empty on purpose — the real value is injected from `app.config.settings` in `env.py`)

- [ ] **Step 3: Wire `env.py` to `app.config.settings`**

Replace the full contents of `backend/alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate the baseline revision**

Run: `uv run alembic revision -m "baseline" --rev-id 0001` (from `backend/`)
Expected: creates `backend/alembic/versions/0001_baseline.py`.

- [ ] **Step 5: Confirm the generated revision file**

Open `backend/alembic/versions/0001_baseline.py` and confirm it matches (the `Create Date` will differ — that's fine):

```python
"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

- [ ] **Step 6: Verify the migration chain (no DB connection needed)**

Run: `uv run alembic heads` (from `backend/`)
Expected: `0001 (head)`

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat(backend): add alembic baseline migration"
```

- [ ] **Step 8: Manual note — not scriptable here**

Once `backend/.env` has a real `DATABASE_URL` pointing at the reachable homelab
Postgres, run `uv run alembic upgrade head` from `backend/` to stamp the
database with revision `0001`. This requires network access to the homelab
and cannot be verified from a sandboxed execution environment — do this step
yourself once the environment is set up.

---

### Task 4: Frontend Scaffolding + Health Test Screen

**Files:**
- Create: `frontend/` (via `npm create vite@latest`) — `package.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, `src/main.tsx`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Create: `frontend/src/index.css`
- Create: `frontend/components.json` (via shadcn init)
- Create: `frontend/src/lib/utils.ts` (via shadcn init)
- Create: `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/card.tsx` (via shadcn add)
- Modify: `frontend/src/App.tsx`
- Create: `frontend/.env.example`
- Create: `frontend/Dockerfile`

**Interfaces:**
- Produces: nothing consumed by other backend tasks. Task 5's docker-compose builds `frontend/Dockerfile`.

- [ ] **Step 1: Scaffold the Vite project**

Run (from repo root): `npm create vite@latest frontend -- --template react-ts`
Expected: creates `frontend/` with the Vite React-TS template.

- [ ] **Step 2: Install base dependencies**

Run: `cd frontend && npm install`
Expected: exits 0, creates `frontend/node_modules/` and `frontend/package-lock.json`.

- [ ] **Step 3: Install Tailwind CSS v4**

Run: `npm install tailwindcss @tailwindcss/vite`
Expected: exits 0, adds both packages to `package.json` dependencies.

- [ ] **Step 4: Wire Tailwind + the `@` path alias into Vite**

Replace `frontend/vite.config.ts` with:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 5: Add the matching path alias to TypeScript config**

In `frontend/tsconfig.app.json`, add inside `compilerOptions`:

```json
"baseUrl": ".",
"paths": {
  "@/*": ["./src/*"]
}
```

- [ ] **Step 6: Import Tailwind in the global stylesheet**

Replace the contents of `frontend/src/index.css` with:

```css
@import "tailwindcss";
```

- [ ] **Step 7: Initialize shadcn/ui**

Run: `npx shadcn@latest init -d`
Expected: exits 0, creates `frontend/components.json` and `frontend/src/lib/utils.ts`.

- [ ] **Step 8: Add the button and card components**

Run: `npx shadcn@latest add button card`
Expected: exits 0, creates `frontend/src/components/ui/button.tsx` and `frontend/src/components/ui/card.tsx`.

- [ ] **Step 9: Write the health test screen**

Replace `frontend/src/App.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type HealthStatus = "checking" | "ok" | "error";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function App() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => setStatus(response.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const statusColor =
    status === "ok" ? "text-green-600" : status === "error" ? "text-red-600" : "text-gray-500";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <Card className="w-80">
        <CardHeader>
          <CardTitle>Handoff — Backend Health</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={statusColor}>
            {status === "checking" && "Checking..."}
            {status === "ok" && "✓ Connected"}
            {status === "error" && "✗ Unreachable"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default App;
```

- [ ] **Step 10: Create the env template**

Create `frontend/.env.example`:

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 11: Verify the build compiles**

Run: `npm run build` (from `frontend/`)
Expected: exits 0, no TypeScript errors, creates `frontend/dist/`.

- [ ] **Step 12: Create the Dockerfile**

Create `frontend/Dockerfile`:

```dockerfile
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
```

- [ ] **Step 13: Commit**

```bash
git add frontend
git commit -m "feat(frontend): scaffold vite react app with health check screen"
```

---

### Task 5: docker-compose Wiring

**Files:**
- Create: `infra/docker-compose.yml`

**Interfaces:**
- Consumes: `backend/Dockerfile` (Task 2), `frontend/Dockerfile` (Task 4)

- [ ] **Step 1: Create `infra/docker-compose.yml`**

```yaml
services:
  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ../backend/.env
    volumes:
      - ../backend:/app
      - /app/.venv

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    env_file:
      - ../frontend/.env
    volumes:
      - ../frontend:/app
      - /app/node_modules
    depends_on:
      - backend
```

- [ ] **Step 2: Prepare local env files (manual, contains real credentials)**

Copy `backend/.env.example` to `backend/.env` and fill in the real homelab
`DATABASE_URL`. Copy `frontend/.env.example` to `frontend/.env` (default
`VITE_API_URL` is fine as-is). These files are gitignored — do this yourself,
it isn't scripted.

- [ ] **Step 3: Bring the stack up**

Run: `docker-compose -f infra/docker-compose.yml up --build -d`
Expected: both containers build and start, command exits 0.

- [ ] **Step 4: Verify the frontend is served**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173`
Expected: `200`

- [ ] **Step 5: Verify the backend health endpoint responds**

Run: `curl -s http://localhost:8000/health`
Expected: a JSON body with a `"status"` key equal to `"ok"` or `"error"`.
Either is a valid outcome here — `"error"` means the homelab Postgres isn't
reachable from inside the Docker network, which is a network/environment
condition to fix on your side, not a bug in this code.

- [ ] **Step 6: Tear the stack down**

Run: `docker-compose -f infra/docker-compose.yml down`
Expected: containers stopped and removed, command exits 0.

- [ ] **Step 7: Commit**

```bash
git add infra/docker-compose.yml
git commit -m "feat(infra): add docker-compose for backend and frontend"
```
