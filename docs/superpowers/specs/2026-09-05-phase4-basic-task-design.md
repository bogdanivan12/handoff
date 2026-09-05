# Phase 4 — Basic Task (manual, no AI) — Design

Sub-project of [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Phase 4. Adds
`Task` (the smallest unit of work, linking Feature + Project + optional
Sprint) and `AcceptanceCriterion` (basic/gherkin), plus the first
split-view panel UI pattern — every prior phase used full-page navigation.

## Context

Phase 3 (merged) built KnowledgeItem/KnowledgeRelation. `schema.sql`
already defines `tasks` and `acceptance_criteria`; `HANDOFF_SPEC.md` §4.1
adds `task_type` and `position` on top of the base `tasks` shape (the
spec's own listing of an "impact" field under Task §4.1 is a documentation
note pointing at Feature's own field per §4.3, not a real Task column —
not implemented here). Task reuses the exact same per-Product issue-number
counter Feature uses (`app.issue_numbers.allocate_issue_number`, built in
Phase 1) — `HAND-12` and `HAND-13` can be a Feature and a Task
respectively, sharing one sequence.

Tasks belong to a Feature, but no page currently shows a Feature's own
detail — Phase 1 only went Product → Initiative → Epic, listing Features
as plain (non-clickable) cards on the Epic page. This phase adds a fifth
hierarchy level, `FeatureDetailPage`, and makes Feature cards clickable
links to it.

## Three deliberate deviations from `schema.sql`

Same pattern as prior phases — deferring columns that depend on tables
that don't exist yet:

- **`tasks.generated_from_draft_id` is not added this phase.** It FKs to
  `task_drafts`, which doesn't exist until Phase 6. Added then, with its
  real FK constraint (matching how Phase 2 added Feature's deferred
  `default_project_id` FK once `projects` existed).
- **`acceptance_criteria.task_draft_id` and its polymorphic `CHECK` are
  not added this phase.** `task_id` is `NOT NULL` for now (not nullable +
  CHECK) since every `AcceptanceCriterion` in this phase belongs to a real
  Task — there are no drafts yet to attach one to instead. Phase 6/7
  relaxes `task_id` to nullable and adds the CHECK when `task_drafts`
  exists.
- **`tasks.relevant_knowledge JSONB DEFAULT '[]'` IS added this phase**,
  unlike the two deferrals above — it isn't blocked by a missing table or
  an unsolved cross-dialect problem (Phase 3 already solved JSON/JSONB
  portability). It stays `[]` for every Task created here; Phase 8 is what
  actually populates it.

## Data model & migration

New Alembic revision, `down_revision = "0004"`:

```
tasks
  id, feature_id FK->features (CASCADE), project_id FK->projects (RESTRICT),
  sprint_id FK->sprints (SET NULL, nullable),
  title TEXT NOT NULL,
  task_type TEXT NOT NULL,        -- feature | bug | improvement | chore | research
  status TEXT NOT NULL DEFAULT 'todo',   -- todo | in_progress | done | outdated
  issue_number INTEGER NOT NULL,  -- from the SAME counter as Feature
  outdated_reason TEXT,
  superseded_by_task_id UUID FK->tasks (SET NULL, nullable, self-referential — inert until Phase 16)
  context TEXT, scope TEXT, out_of_scope TEXT,
  position INTEGER,               -- nullable, no auto-assignment this phase (Phase 11/12 concern)
  relevant_knowledge JSONB NOT NULL DEFAULT '[]',   -- inert until Phase 8
  created_at, updated_at

acceptance_criteria
  id, task_id FK->tasks (CASCADE, NOT NULL — see deviation above)
  format TEXT NOT NULL DEFAULT 'basic',   -- basic | gherkin
  description TEXT,               -- used when format=basic
  given TEXT, when_ TEXT, then_ TEXT,   -- used when format=gherkin
  position INTEGER NOT NULL DEFAULT 0,
  checked BOOLEAN NOT NULL DEFAULT false,
  checked_at TIMESTAMPTZ, checked_by UUID,   -- inert, no auth in the MVP
  notes TEXT,
  created_at
```

`issue_number`/`issue_key` for Task work exactly like Feature's: creating
a Task calls the same `allocate_issue_number(db, product_id)` helper
(Phase 1), with `product_id` resolved by walking `feature → epic →
initiative → product`. `issue_key` is computed the same way
(`f"{product.key_prefix}-{issue_number}"`), so Tasks and Features share
one visible numbering sequence per Product.

## Backend

- `Task` and `AcceptanceCriterion` SQLAlchemy models, following established
  conventions (`GUID` ids, `Text` for enum-like fields, matching
  `default=`/`server_default=` pairs from the start).
- `POST /tasks` validates `feature_id` (404), `project_id` (404), and
  `sprint_id` if given (404) all exist, then allocates the issue number
  and creates the Task in one transaction — same shape as Feature's
  `create_feature`.
- `GET /tasks?feature_id=` — flat REST, filtered list, same convention as
  every other resource so far.
- `GET/PATCH/DELETE /tasks/{id}` — PATCH covers `title`, `task_type`,
  `status`, `context`, `scope`, `out_of_scope`, `sprint_id`,
  `position` — not `feature_id`/`project_id`/`issue_number` (immutable
  after creation, same as Feature's `epic_id`/`issue_number`).
- `AcceptanceCriterion` CRUD is **nested** under
  `/tasks/{task_id}/acceptance-criteria` — the one deliberate deviation
  from this project's flat-REST convention so far, because an
  AcceptanceCriterion has no meaning or lookup path independent of its
  Task (unlike Initiative/Epic/Feature, which are independently
  addressable resources with their own detail views).
  `GET/POST /tasks/{task_id}/acceptance-criteria`,
  `PATCH/DELETE /tasks/{task_id}/acceptance-criteria/{id}` (PATCH covers
  `checked`, `description`/`given`/`when_`/`then_`, `position`).

## Testing

Same in-memory SQLite fixture, reused verbatim. Coverage per resource:
create/list/get/update/delete for Task, plus a test proving Task and
Feature share one counter (create a Feature then a Task under the same
Product, confirm sequential issue numbers) and one test per
AcceptanceCriterion CRUD path.

## Frontend

- **New `FeatureDetailPage`** (`/products/:productId/initiatives/:initiativeId/epics/:epicId/features/:featureId`)
  — lists the Feature's Tasks (issue_key badge + task_type badge), with a
  breadcrumb extending to 5 levels and a "New Task" button.
- **`EpicDetailPage`'s Feature cards become links** to the new page
  (currently plain, non-clickable `Card`s).
- **Split-view panel** (first use of this pattern): clicking a Task (or
  "New Task") opens a side panel — plain local component state, no URL
  change, no new route — showing/editing the Task's fields (title,
  task_type, status, context) and its Acceptance Criteria (list with
  checkbox toggle, inline add form, basic/gherkin format toggle per the
  spec's "toggle basic/gherkin" line). One component handles both create
  and edit mode.

## What we are NOT building in Phase 4

- `TaskDraft`, `GeneratedPrompt`, `AgentSession` (later phases)
- Any board/Kanban/backlog view using `position`/`status` visually
  (Phase 11) — `position` is just a plain settable field this phase, no
  auto-assignment or drag-and-drop
- `TaskDependency` (Phase 5) — nothing here blocks a Task from being
  "ready"; that's the next phase
- Marking a Task `outdated` or setting `superseded_by_task_id` (Phase 16)
  — the columns exist, inert
- Tags/labels on Task (§4.6 of the general spec, not tied to this phase)

## Open risks / assumptions

- `AcceptanceCriterion`'s nested-route deviation from flat REST is
  deliberate, not an oversight — don't "fix" it to match the flat
  convention in a later phase without re-reading this rationale
- The split-view panel is plain local state today (no URL reflection,
  not bookmarkable/shareable) — acceptable per YAGNI since nothing yet
  needs a shareable deep link to one Task; revisit only if that need
  actually arises
