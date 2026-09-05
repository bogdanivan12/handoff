# Phase 3 — Knowledge Model — Design

Sub-project of [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Phase 3. Adds
`KnowledgeItem` (a typed fact scoped to a Product or a Project) and
`KnowledgeRelation` (a directed link between two facts) — the first phase
to introduce a JSON-shaped column and the first real test of the
SQLite-vs-Postgres divergence risk Phase 1's design doc flagged.

## Context

Phase 2 (merged) added Project/Sprint, both scoped to a Product. Knowledge
is scoped similarly but to either a Product OR a Project (`schema.sql`'s
`scope` + `scope_ref_id` pair), and `content`'s shape depends on `type` —
one of 6 fixed kinds (`decision`, `convention`, `constraint`,
`domain_concept`, `technical_fact`, `known_issue`), each with its own field
set per `schema.sql`'s comment block.

## Two deliberate deviations from `schema.sql`

- **No `embedding vector(1536)` column.** `pgvector` is prepared on the
  Postgres side (extension installed, per Phase 0) but genuinely unused —
  HANDOFF_SPEC.md §7 explicitly excludes active vector search from the
  MVP. SQLite has no native vector type, so adding this column now would
  mean solving a real cross-dialect problem for a column nothing reads or
  writes. It's added in whichever future phase actually activates vector
  search, not here.
- **`type`, `scope`, `provenance`, `status`, `relation_type` are plain
  `Text` columns, not Postgres `ENUM`s** — the same simplification Phases
  1-2 already applied to `Feature.status`/`Sprint.status`. Valid values
  are enforced at the Pydantic layer.

## Data model & migration

New Alembic revision, `down_revision = "0003"`:

```
knowledge_items
  id, type TEXT NOT NULL,           -- derived server-side from content's discriminator, see below
  scope TEXT NOT NULL,              -- 'product' | 'project'
  scope_ref_id GUID NOT NULL,       -- product_id or project_id, validated at create time (see Backend)
  content JSONB NOT NULL,           -- JSONB on Postgres, JSON on SQLite via `.with_variant(...)`
  confidence NUMERIC(3,2) nullable,
  provenance TEXT NOT NULL DEFAULT 'manual',
  source_ref_type TEXT nullable,    -- 'task' | 'agent_session' | NULL — no FK yet, neither table exists
  source_ref_id GUID nullable,
  status TEXT NOT NULL DEFAULT 'active',
  created_at, updated_at

knowledge_relations
  id, from_item_id GUID FK->knowledge_items (CASCADE),
  to_item_id GUID FK->knowledge_items (CASCADE),
  relation_type TEXT NOT NULL,      -- 'supersedes' | 'conflicts_with' | 'derived_from' | 'refines'
  created_at,
  CHECK (from_item_id != to_item_id)
```

`content`'s column type: `JSONB().with_variant(JSON(), "sqlite")` —
SQLAlchemy's built-in cross-dialect mechanism (no custom `TypeDecorator`
needed, unlike `GUID`, since `with_variant` covers this case directly).

## The discriminated union, and how `type` gets derived

Six Pydantic content models, each carrying its own literal `kind` field as
the discriminator (matching `schema.sql`'s per-type field lists, e.g.
`DecisionContent` has `subject`/`chosen`/`alternatives_considered`/
`rationale`):

```python
KnowledgeContent = Annotated[
    Union[DecisionContent, ConventionContent, ConstraintContent,
          DomainConceptContent, TechnicalFactContent, KnownIssueContent],
    Field(discriminator="kind"),
]
```

`KnowledgeItemCreate` takes only `scope`, `scope_ref_id`, `content`
(typed as `KnowledgeContent`) — **not** a separate `type` field. The
server derives `type` from `content.kind` when storing, so the two can
never disagree. This means the persisted `content` JSONB blob carries one
extra key (`kind`) beyond what `schema.sql`'s comment lists — necessary so
a stored item can be deserialized back into the correct variant on read,
using Pydantic's own discriminated-union mechanism both ways.

## Backend

- `POST /knowledge-items` validates `scope_ref_id` resolves to a real
  Product (if `scope="product"`) or Project (if `scope="project"`) before
  writing — 404 if not, matching the pattern established in Phases 1-2.
- `GET /knowledge-items?scope=&scope_ref_id=` — filtered list, flat REST
  as usual.
- `GET/PATCH/DELETE /knowledge-items/{id}` — PATCH accepts `content`
  (full replace of the JSONB blob, re-deriving `type`) and/or `status`.
- `POST /knowledge-relations` validates both `from_item_id` and
  `to_item_id` exist (404 if not) and that they differ (422, checked at
  the app layer before ever reaching the DB's `CHECK` constraint).
- `GET /knowledge-relations?from_item_id=` and `?to_item_id=` (either
  filter, not both) for listing relations touching one item.
- No `PATCH` for relations — a relation is a fact about two items, not an
  editable record; delete and recreate if it's wrong.

## Testing

Continues on the same in-memory SQLite fixture from Phases 1-2 — the
`content` field round-trips as a plain Python `dict` through JSON on both
dialects (this is exactly what `with_variant` buys us, and doesn't touch
any Postgres-only JSONB feature like containment operators or GIN
indexing, so SQLite is a faithful stand-in for what this phase actually
exercises). The controller's now-established practice of a manual
live smoke test against the real homelab Postgres (as done for Phases 1-2)
remains the way real-Postgres behavior gets verified before merge — this
phase doesn't need a new automated Postgres-backed test tier, since
nothing here is JSONB-specific in behavior, only in storage.

## Frontend

- New route `/products/:productId/knowledge` → `ProductKnowledgePage`.
- A scope selector: "Product-level" (default — `scope=product`,
  `scope_ref_id=productId`) or one entry per Project under this Product
  (`scope=project`, `scope_ref_id=project.id`), reusing the Projects list
  already fetched for the Settings page's pattern.
- List: each item shows a `type` badge and a one-line summary pulled from
  its `content` (e.g. Decision shows `content.chosen`, Constraint shows
  `content.rule`, Known Issue shows `content.description`) — not the full
  JSON blob.
- Create form: a `type` `<select>` that switches which fields render
  below it (the fields for whichever content variant is selected), same
  "inline toggle form" pattern as every other page so far.
- No dedicated UI for `KnowledgeRelation` in this phase — the API exists
  (needed for Phase 9's Agent Session extraction to link facts), but a
  relation-picker UI is deferred; not called for by this phase's spec
  line ("listă filtrabilă pe scope, formular dinamic per tip" only
  describes the KnowledgeItem UI).

## What we are NOT building in Phase 3

- Vector embeddings / semantic search (see deviation above)
- Any UI for creating/viewing `KnowledgeRelation`s
- Knowledge extraction from Tasks or Agent Sessions (Phases 6, 9) — this
  phase only builds the manual CRUD + provenance/source columns those
  phases will populate later
- `KnowledgeRelation` validation beyond existence + `from != to` — no
  cycle detection, no semantic checking that a `supersedes` link makes
  sense

## Open risks / assumptions

- `content`'s `kind` field duplicating the `type` column is a deliberate,
  minor redundancy (not normalized away) — it's what makes Pydantic's
  discriminated union work symmetrically on write and read. A future
  phase should not "clean this up" by removing `kind` from the stored
  JSON; that would break deserialization.
- No FK on `source_ref_id` (correct — `tasks`/`agent_sessions` don't exist
  yet). Phase 4 and Phase 9 do NOT need to add this FK retroactively
  (unlike Phase 1→2's `default_project_id` situation) because
  `source_ref_type` distinguishes which table it would point to, and a
  single polymorphic FK isn't expressible as a normal DB constraint anyway
  — this stays app-validated indefinitely, same as `schema.sql` already
  implies ("validat la app-level").
