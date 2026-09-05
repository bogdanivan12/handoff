# Phase 5: Dependencies — Design

**Spec source:** `HANDOFF_SPEC.md` §Phase 5 ("CRUD TaskDependency + FeatureDependency. Endpoint `GET /tasks/{id}/is-blocked`... UI: visual display (lock/grayed-out on blocked tasks in the board).") and §4.2/§4.4 (data shapes).

## Context and scope

Phase 5 adds two dependency-edge entities — `TaskDependency` (task → task) and
`FeatureDependency` (feature → feature) — plus a computed "is this task
blocked" check. The spec's own UI language ("in the board") assumes the
Kanban board, which is Phase 11 and does not exist yet. This design adapts
the UI to the surfaces that exist today: `FeatureDetailPage`'s Task list and
the `TaskPanel`/`FeatureDetailPage` side panels (both built in Phase 4).

**Deliberate deviation from `schema.sql`, corrected here:** `schema.sql` has
no `task_dependencies`/`feature_dependencies` tables at all (unlike every
prior phase, where the tables already existed and this project only read
schema.sql). This design adds them to `schema.sql`, mirroring the existing
`knowledge_relations` table's conventions exactly (self-link `CHECK`, two
indexes, no uniqueness constraint, no cross-row cycle detection). Feature's
`impact`/`effort`/`priority`/`success_looks_like` columns (spec §4.3) are
**not** added in this phase — nothing in Phase 5's checklist uses them, and
they're only consumed starting Phase 11's Impact/Effort Matrix. Adding them
now would violate "each phase is a complete, testable vertical slice."

**No cycle detection.** The spec requires only the self-reference guard
(`task_id != depends_on_task_id` / `feature_id != depends_on_feature_id|`).
A general graph-cycle check is not requested and edges toward the
explicitly excluded "interactive graph editor for dependencies" (spec §7).
`is-blocked` only inspects a task's direct dependencies' `status`, so a
cycle (if one were created) cannot cause an infinite loop there — it only
means both tasks could show as blocked, which is honest given a genuine
circular dependency.

## Data model

```sql
CREATE TABLE task_dependencies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (task_id != depends_on_task_id)
);

CREATE INDEX idx_task_dependencies_task ON task_dependencies(task_id);
CREATE INDEX idx_task_dependencies_depends_on ON task_dependencies(depends_on_task_id);

CREATE TABLE feature_dependencies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  depends_on_feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (feature_id != depends_on_feature_id)
);

CREATE INDEX idx_feature_dependencies_feature ON feature_dependencies(feature_id);
CREATE INDEX idx_feature_dependencies_depends_on ON feature_dependencies(depends_on_feature_id);
```

Both FKs on both tables are `ON DELETE CASCADE`: deleting a Task or Feature
should remove dependency edges that reference it in either direction —
consistent with how every other join-style table in this project cascades
(e.g. `knowledge_relations`, `acceptance_criteria`).

## Backend

### Nested REST for dependency edges

Same exception-precedent as `AcceptanceCriterion` (Phase 4): a dependency
edge has no meaning independent of the task/feature that owns it.

- `GET /tasks/{task_id}/dependencies` → list of `TaskDependencyRead`, each
  expanding the depended-on task's `id`, `issue_key`, `title`, `status` (so
  the frontend never needs a second round-trip per row).
- `POST /tasks/{task_id}/dependencies` `{depends_on_task_id}` → 201. 404 if
  either task doesn't exist. 400 if `depends_on_task_id == task_id`
  (defense in depth — the DB `CHECK` also catches this, but a clean 400
  beats a raw `IntegrityError` 500, matching this project's existing
  precedent of pre-checking constraints the ORM can't catch cleanly,
  established in Phase 4's final review for the Project/Task RESTRICT FK).
- `DELETE /tasks/{task_id}/dependencies/{dependency_id}` → 204. 404 if the
  dependency doesn't exist or doesn't belong to `task_id` (same ownership
  guard pattern as `AcceptanceCriterion`).
- `GET /tasks/{task_id}/is-blocked` → `{"is_blocked": bool, "blocking_tasks": [{"id", "issue_key", "title", "status"}]}`.
  `blocking_tasks` includes only dependencies whose `status != "done"` — an
  empty list means `is_blocked` is `false`.

Same four shapes for `/features/{feature_id}/dependencies`, minus
`is-blocked` (spec doesn't request a Feature-level blocked check — Feature
"blocked" isn't a stated concept, only Task).

### Product-scoped list filters (for the dependency pickers)

The dependency picker needs to search tasks/features across the whole
Product (per the chosen design), not just the current Feature/Epic. Extend
the existing list endpoints rather than add new ones:

- `GET /tasks` currently requires `feature_id`. It gains an alternate
  `product_id` filter — exactly one of `feature_id`/`product_id` is
  required (400 if neither or both given). `product_id` mode joins
  Task → Feature → Epic → Initiative → Product.
- `GET /features` currently requires `epic_id`. Same treatment: alternate
  `product_id` filter, joining Feature → Epic → Initiative → Product.

### `is_blocked` on `TaskRead`

To render a lock icon on the existing Task list without N+1 calls,
`TaskRead` gains a computed `is_blocked: bool`, computed via a correlated
`EXISTS` subquery (any `task_dependencies` row for this task whose
`depends_on_task_id` points to a task with `status != 'done'`) — added at
the same point every `TaskRead` response is currently built (`_EAGER_LOAD`
in `tasks.py`), not a separate call.

## Frontend

- **`TaskPanel`** (Phase 4): new "Depends on" section below Acceptance
  Criteria. Lists current dependencies (issue_key + title + status badge),
  each with a remove button. Below that, an "Add dependency" `<select>`
  populated from `GET /tasks?product_id=`, filtered client-side to exclude
  the task itself and already-added dependencies.
- **`FeatureDetailPage`** (Phase 4): same pattern, a new "Depends on"
  section backed by `GET /features?product_id=`.
- **Task list in `FeatureDetailPage`**: rows where `task.is_blocked` render
  with reduced opacity and a small lock icon next to the issue-key badge.

## Testing

- Backend: dependency CRUD (create/list/delete, ownership-mismatch 404,
  self-reference 400), `is-blocked` (no deps → false; one done dep → false;
  one non-done dep → true with correct `blocking_tasks`), product-scoped
  list filters (both filters together → 400, neither → 400), cascade
  delete (deleting a task removes dependency rows referencing it in either
  direction).
- Frontend: TaskPanel/FeatureDetailPage render the new section, add/remove
  a dependency round-trips through the API, blocked-task row styling.
- Live smoke test against real Postgres (established pattern every phase):
  verify the new tables/constraints against actual Postgres, not just
  SQLite.
