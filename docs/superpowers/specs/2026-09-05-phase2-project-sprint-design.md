# Phase 2 — Project & Sprint — Design

Sub-project of [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Phase 2. Adds the
delivery-side concepts (Project, Sprint) on top of Phase 1's product
hierarchy, both scoped to a Product rather than nested under
Initiative/Epic/Feature.

## Context

Phase 1 (merged) built Product → Initiative → Epic → Feature CRUD with a
computed `issue_key` on Feature. `schema.sql` already defines `projects`
(FK to `products`) and `sprints` (FK to `products`, "sprint mereu la nivel
de Product" — never at Project level) tables. Phase 1's `features` table
has a `default_project_id` column with no FK constraint yet, because
`projects` didn't exist at the time — Phase 1's design doc flagged this
explicitly as a Phase 2 follow-up.

## Data model & migration

New Alembic revision, `down_revision = "0002"`:

```
projects
  id, product_id FK->products (CASCADE), name, description,
  created_at, updated_at

sprints
  id, product_id FK->products (CASCADE), name,
  start_date DATE nullable, end_date DATE nullable,
  status TEXT NOT NULL DEFAULT 'planned',   -- planned | active | completed, plain Text (no enum), same simplification as Feature.status in Phase 1
  created_at, updated_at
```

Same migration also adds the FK constraint Phase 1 deferred:
`features.default_project_id` → `projects.id` `ON DELETE SET NULL`. This
requires updating `Feature.default_project_id`'s `mapped_column` in
`app/models.py` to declare the `ForeignKey` (it's currently a bare `GUID`
column with no FK).

## Backend

- SQLAlchemy models for `Project`/`Sprint`, same shape as Phase 1's
  Initiative/Epic (a `product_id` FK, `back_populates` on both sides).
- Pydantic `Create`/`Update`/`Read` schemas per entity, appended to
  `app/schemas.py`.
- Flat REST routers, one file per resource:
  - `GET /projects?product_id=`, `POST /projects`, `GET/PATCH/DELETE /projects/{id}`
  - `GET /sprints?product_id=`, `POST /sprints`, `GET/PATCH/DELETE /sprints/{id}`
- `POST /projects` and `POST /sprints` both check the parent Product exists
  before creating (matching the 404-not-500 pattern Phase 1's final review
  established for Initiative/Epic).
- No new business logic beyond plain CRUD — no counters, no computed
  fields, unlike Phase 1's Feature.

## Testing

Same in-memory SQLite fixture from Phase 1, reused verbatim. Coverage per
resource: create, list (filtered by `product_id`), get by id, update,
delete, plus a create-with-missing-product 404 test for both resources
(mirroring Phase 1's Initiative/Epic tests).

## Frontend

- New route `/products/:productId/settings` → `ProductSettingsPage`, with
  two sections (Projects, Sprints), each with its own list + inline create
  form — deliberately separate from the Initiative/Epic/Feature drill-down
  pages, since Project/Sprint are a parallel "delivery" axis, not part of
  that hierarchy.
- A "Settings" link added to `ProductDetailPage`'s header area, next to the
  existing breadcrumb, linking to this new page.
- Sprint's create form includes `start_date`/`end_date` as plain HTML
  `<input type="date">` (optional — Sprint's dates are nullable) and no
  `status` input (defaults to `"planned"` server-side; changing status is
  out of scope for this phase's create-only forms, same restraint as
  Phase 1's pages).

## What we are NOT building in Phase 2

- Any board/filter UI that uses Project or Sprint (Kanban/Sprint/Matrix
  views are Phase 11)
- Any way to link a Task to a Project/Sprint (Task doesn't exist until
  Phase 4)
- A UI to set `Feature.default_project_id` — only the DB-level FK lands
  this phase; wiring it into the Feature UI is deferred until it's
  actually needed
- Sprint status transitions/UI (planned → active → completed) — the
  column exists with a default, but no UI to change it yet

## Open risks / assumptions

- None beyond what Phase 1 already recorded (SQLite-vs-Postgres test
  divergence risk, still low for this phase's equally portable schema)
