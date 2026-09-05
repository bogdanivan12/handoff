# Phase 1 — Product Hierarchy + Issue Keys — Design

Sub-project of [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Phase 1. Builds the
first real domain slice on top of Phase 0's scaffolding: CRUD for the
Product → Initiative → Epic → Feature hierarchy, plus auto-generated issue
keys (`HAND-123`) on Features.

## Context

Phase 0 (merged) gave us a working FastAPI + SQLAlchemy async backend with a
`/health` endpoint and an empty Alembic baseline (`0001`, no tables), and a
Vite/React/TS frontend with Tailwind + shadcn/ui but no routing yet — a
single test screen. `schema.sql` already defines the base shape of
`products`, `initiatives`, `epics`, `features`; `HANDOFF_SPEC.md` §4.7 adds
`key_prefix` (Product) and `issue_number` (Feature) on top of that base
shape, with a single counter per Product shared conceptually between
Feature and Task issue numbers (Task itself doesn't exist until Phase 4 —
this phase only wires up Feature's use of that counter).

## Data model & migration

New Alembic revision, `down_revision = "0001"`, creating four tables from
`schema.sql` plus the two new fields:

```
products
  id, name, description, acceptance_criteria_format_default,
  key_prefix TEXT NOT NULL,
  next_issue_number INTEGER NOT NULL DEFAULT 1,   -- internal counter, never exposed directly
  created_at, updated_at

initiatives
  id, product_id FK->products, name, description, created_at, updated_at

epics
  id, initiative_id FK->initiatives, name, description, created_at, updated_at

features
  id, epic_id FK->epics, default_project_id FK->projects (nullable, projects
    table doesn't exist until Phase 2 — column added now per schema.sql but
    left unused/always NULL until then),
  name, requirements, status, acceptance_criteria_format,
  issue_number INTEGER NOT NULL,
  created_at, updated_at
```

`issue_number` is assigned at Feature creation by atomically incrementing
the parent Product's `next_issue_number` in the same transaction as the
insert:

```sql
UPDATE products SET next_issue_number = next_issue_number + 1
WHERE id = :product_id RETURNING next_issue_number;
```

The resulting value becomes the new Feature's `issue_number`. This keeps
the counter monotonic per Product without a dynamically-created Postgres
sequence per row (simpler migrations, no per-row DDL).

`issue_key` (e.g. `HAND-12`) is **not stored**. It's computed at read time
by joining Feature → Epic → Initiative → Product and formatting
`f"{product.key_prefix}-{feature.issue_number}"`.

## Backend

- SQLAlchemy 2.0 async models for all four tables, following the pattern
  established in Phase 0's `app/db.py`.
- Pydantic schemas per entity: a `Create` shape (input), and a `Read` shape
  (output) — Feature's `Read` schema additionally carries a computed
  `issue_key: str` field.
- Flat REST routers, one file per resource, mirroring the schema's FK
  shape rather than deep nested URLs:
  - `GET /products`, `POST /products`, `GET/PATCH/DELETE /products/{id}`
  - `GET /initiatives?product_id=`, `POST /initiatives`, `GET/PATCH/DELETE /initiatives/{id}`
  - `GET /epics?initiative_id=`, `POST /epics`, `GET/PATCH/DELETE /epics/{id}`
  - `GET /features?epic_id=`, `POST /features`, `GET/PATCH/DELETE /features/{id}`
- `POST /features` is the one non-trivial handler: it must run the counter
  increment and the insert in the same DB transaction, and the response
  includes the computed `issue_key`.
- Reuses `get_db` from Phase 0 (`app/db.py`), unchanged.

## Testing

No local Postgres, and the homelab instance isn't reliably reachable from
an automated test run — so backend tests use an in-memory SQLite database
(`aiosqlite` driver) via a pytest fixture: a fresh async engine per test
session, tables created directly from SQLAlchemy metadata
(`Base.metadata.create_all`), with `get_db` overridden to yield a SQLite
session instead of the real Postgres one. This works because Phase 1's
tables use only portable column types (no `JSONB`, no `pgvector`) — a later
phase (Knowledge model, Phase 3) that needs Postgres-specific types will
need to revisit this (likely an ephemeral Postgres test container at that
point), noted as a future risk, not solved here.

Coverage per resource: create, list (filtered by parent id), get by id,
update, delete. Plus one Feature-specific test proving the numbering
behavior: two Features created under the same Product get sequential
`issue_number` (1, 2, ...); a Feature under a *different* Product starts
its own count at 1.

## Frontend

- Introduces `react-router-dom` — Phase 0 had exactly one screen and no
  router at all.
- Routes: a Products list/switcher at `/`, then drill-down routes for
  Initiatives/Epics/Features under a selected Product
  (`/products/:productId`, `/products/:productId/initiatives/:initiativeId`,
  etc.) — URL nesting here is just for browser navigation state, not the
  API shape (which stays flat, per above).
- A breadcrumb component derived from the current route params, showing
  `Product > Initiative > Epic > Feature` with whichever levels are
  currently selected.
- A "New Product" form (name, description, key_prefix) — Phase 15's
  onboarding/seeding doesn't exist yet, so this is the only way to get a
  Product into the system through the UI. Equivalent minimal create forms
  at each level (Initiative under a Product, Epic under an Initiative,
  Feature under an Epic) so the hierarchy is actually buildable end-to-end
  through the UI, not just via API calls.
- Feature rows/cards show their computed `issue_key` badge (e.g. `HAND-12`)
  next to the name, per `HANDOFF_SPEC.md` §6's "issue keys shown everywhere
  a Task/Feature appears" convention.

## What we are NOT building in Phase 1

- Any Project/Sprint concept (Phase 2)
- Any Task/TaskDraft (Phase 4+)
- Drag-and-drop, boards, or any Kanban/Sprint/Matrix view (Phase 11)
- Polished Jira-like styling beyond functional navigation + breadcrumb —
  visual polish is incremental across phases, not a one-shot effort here
- Any onboarding/sample-data seeding (Phase 15) — the "New Product" form is
  the stand-in until then

## Open risks / assumptions

- SQLite-based tests won't catch Postgres-specific behavior differences
  (e.g. constraint error message shapes) — acceptable for this phase's
  portable schema, revisit when `JSONB`/`pgvector` types are introduced
- The atomic counter increment relies on the Feature insert and the
  Product counter update sharing one transaction — a future phase adding
  more issue-number consumers (Task, Phase 4) must follow the same
  pattern, not invent a second counter
