# Handoff — Project Spec

Product & project management platform, product-centric, built for the era of AI-assisted development. It doesn't execute tasks — it prepares them, structured, ready to hand off to an AI coding agent (Claude Code, Cursor, etc.), and accumulates project memory (facts) that informs future task generation.

This document is the source of truth for implementation. Follow the phases in order — each phase produces a functional vertical slice (DB → API → UI), testable before moving on.

---

## 1. Design principles

- **Human-in-the-loop everywhere** — nothing AI-generated (tasks, facts, changelog) becomes "active" without explicit user approval.
- **Simplicity over completeness** — we prefer a simple, easy-to-use concept over a "correct" but heavy framework (e.g. an Impact/Effort matrix instead of RICE scoring).
- **Product-centric** — every unit of work (feature, bug, improvement, chore, research) links back to a Feature. Nothing "floats" without business context.
- **Jira-like, visually and functionally** — fixed sidebar, issue keys (`HAND-123`), split-view detail panel, drag-and-drop boards, colored badges per type.
- **Snapshot, not live reference** — any context given to an AI at generation time (knowledge, prompt) is saved as an immutable snapshot, not recalculated retroactively.

---

## 2. Tech stack

- **Backend**: Python + FastAPI, SQLAlchemy 2.0 async (or SQLModel), Alembic for migrations
- **DB**: PostgreSQL 15+ with the `pgvector` extension (prepared for future semantic retrieval, not actively used in the MVP)
- **Frontend**: React + TypeScript + Vite, Tailwind CSS + shadcn/ui, `dnd-kit` for drag-and-drop (boards)
- **AI**: LiteLLM (proxy already deployed by the user) — all AI calls go through the configured LiteLLM endpoint, OpenAI-compatible format (`/v1/chat/completions`)
- **Infra**: Docker + docker-compose locally; deploy target on k3s (homelab, Proxmox)
- **Auth**: none in the MVP (single-user). Added later if it becomes multi-user.

---

## 3. Concept glossary

| Concept | Description |
|---|---|
| **Product** | What is being built. Root of the hierarchy. |
| **Initiative** | Strategic goal under a Product. |
| **Epic** | Major product area, under an Initiative. |
| **Feature** | Central unit of refinement. Under an Epic. All Tasks link to a Feature. |
| **Project** | Delivery concept, separate from the product hierarchy. A Feature can produce Tasks for multiple Projects. |
| **Sprint** | Always at the Product level (not Project). Boards can optionally be filtered per Project. |
| **Task** | The smallest unit of work, meant to be handed to an AI agent. Links Feature + Project + Sprint (optional). |
| **TaskDraft** | Task proposed by AI, pending review/approval, before it becomes a real Task. |
| **KnowledgeItem** | Typed fact (decision/convention/constraint/domain_concept/technical_fact/known_issue), scoped to Product or Project. |
| **AgentSession** | Uploaded conversation (user ↔ external AI agent), from which completion status + newly proposed facts are extracted. |
| **Idea Inbox** | Single capture point for any raw idea/bug/improvement, before formal organization. |
| **Next Up Queue** | Computed view: tasks with no unresolved dependencies, ready to send to an AI agent. |

---

## 4. Data model

The base SQL schema already exists (see `schema.sql` — Product, Initiative, Epic, Feature, Project, Sprint, KnowledgeItem, KnowledgeRelation, TaskDraft, Task, AcceptanceCriterion, GeneratedPrompt, AgentSession). Add the following, decided afterward:

### 4.1 Task — new fields

```
Task
  ...(existing fields)
  task_type: feature | bug | improvement | chore | research   -- discriminator
  feature_id NOT NULL   -- remains mandatory regardless of task_type
  impact: low | high     -- nullable, actually only used for Feature — see 4.3
  position INTEGER        -- order in backlog/column, used as default "priority"
```

Note: `task_type` influences:
- the `GeneratedPrompt` template (e.g. `research` requires a conclusion/report-type output, not code)
- color/icon on boards (bug=red, feature=blue, improvement=green, chore=gray, research=purple)
- filtering in Backlog/Board

### 4.2 TaskDependency

```
TaskDependency
  id UUID PK
  task_id UUID FK → tasks
  depends_on_task_id UUID FK → tasks
  created_at
  CHECK (task_id != depends_on_task_id)
```

A task is "eligible" for the Next Up Queue only if all `depends_on_task_id` have `status = done`.

### 4.3 Feature — new fields

```
Feature
  ...(existing fields)
  impact: low | high        -- nullable
  effort: low | high        -- nullable
  priority: low | medium | high | critical   -- nullable, manual override
  success_looks_like TEXT   -- optional, one success sentence (not a full OKR framework)
```

The matrix quadrant (Quick Win / Big Bet / Fill-in / Time Sink) is computed at display time from `impact`+`effort`, not stored.

### 4.4 FeatureDependency

```
FeatureDependency
  id UUID PK
  feature_id UUID FK → features
  depends_on_feature_id UUID FK → features
  created_at
  CHECK (feature_id != depends_on_feature_id)
```

Used for the roadmap timeline (arrows between Features).

### 4.5 IdeaInboxItem

```
IdeaInboxItem
  id UUID PK
  product_id UUID FK → products
  raw_text TEXT NOT NULL
  status: new | promoted | archived
  promoted_to_type: feature | bug | improvement | chore | research | NULL
  promoted_to_feature_id UUID FK → features, NULL
  created_at, updated_at
```

Flow: user writes a raw idea → stays `new` → on promotion, picks type + parent Feature (mandatory) → becomes a real Task (if type ≠ feature) or a new Feature in refinement (if type = feature).

### 4.6 Tags (simple, optional)

```
Tag
  id UUID PK
  product_id UUID FK → products
  name TEXT
  color TEXT

TaskTag
  task_id UUID FK → tasks
  tag_id UUID FK → tags
```

When generating a Task, the AI can suggest 1-3 tags (doesn't create them automatically, only proposes — user accepts/rejects during the TaskDraft review).

### 4.7 Issue key

```
Product
  ...
  key_prefix TEXT NOT NULL  -- e.g. "HAND", configurable at Product creation

Feature / Task
  ...
  issue_number INTEGER  -- sequential per Product, generated at creation
  -- displayed as "{product.key_prefix}-{issue_number}", e.g. HAND-123
```

The sequence can be shared between Feature and Task (a single counter per Product) or separate — recommended: **a single counter per Product**, simpler to implement (a `SERIAL` column or a Postgres sequence per Product), and more natural for referencing (it doesn't matter whether HAND-45 is a Feature or a Task).

---

## 5. Development phases

Each phase = a complete vertical slice (model → endpoint → UI), testable before moving on. Don't jump to AI generation (Phase 6) before 0-5 are solid.

### Phase 0 — Scaffolding
Repo `/backend` (FastAPI), `/frontend` (React+Vite), `/infra` (docker-compose). Backend with async SQLAlchemy + Alembic connected to Postgres. Frontend Vite+React+TS+Tailwind+shadcn with one test screen (`/health`). `docker-compose up` starts everything.

### Phase 1 — Product Hierarchy + Issue Keys
CRUD Product/Initiative/Epic/Feature per schema. Add `key_prefix` on Product and auto-generated `issue_number` (sequence per Product) on Feature. UI: simple hierarchical navigation + breadcrumb.

### Phase 2 — Project & Sprint
CRUD Project (linked to Product) and Sprint (linked to Product, with dates + status). UI: management screen per Product.

### Phase 3 — Knowledge Model
CRUD KnowledgeItem with a Pydantic discriminated union per `type` (6 types, shapes from schema.sql). CRUD KnowledgeRelation (`supersedes`/`conflicts_with`). UI: list filterable by scope, dynamic form per type.

### Phase 4 — Basic Task (manual, no AI)
CRUD Task (`feature_id` mandatory, `task_type` enum, `issue_number` from the same counter as Feature) + AcceptanceCriterion (basic/gherkin toggle). UI: split-view detail panel (clicking a task opens it on the side, no page navigation).

### Phase 5 — Dependencies
CRUD TaskDependency + FeatureDependency. Endpoint `GET /tasks/{id}/is-blocked` (checks whether all dependencies have status=done). UI: visual display (lock/grayed-out on blocked tasks in the board).

### Phase 6 — AI Generation: Feature → TaskDraft
Endpoint `POST /features/{id}/generate-tasks`: collects requirements + knowledge (product+project scope) + existing tasks (if regenerating) → prompt to LiteLLM → strict JSON parsing → creates `task_drafts` + `acceptance_criteria`. AI also suggests `task_type` + tags per draft.

### Phase 7 — Review & Approval
Editing a TaskDraft before approval. `POST /task-drafts/{id}/approve` → creates the real Task, migrates acceptance criteria, builds the `relevant_knowledge` snapshot. `POST /task-drafts/{id}/reject`. UI: review screen with visual diff if it's a regeneration (new task vs. task that became outdated).

### Phase 8 — Generated Prompt
`GET /tasks/{id}/is-ready`, `POST /tasks/{id}/generate-prompt` (template varies slightly per `task_type`). `is_stale=true` automatically on any subsequent edit. UI: disabled button with tooltip if not ready.

### Phase 9 — Agent Session upload & extraction
Upload text/markdown → LiteLLM call for extraction (summary, completion status, proposed facts) → facts as `knowledge_items` with `status=draft` → review + mandatory scope choice on approval.

### Phase 10 — Idea Inbox
CRUD IdeaInboxItem. Promotion endpoint (`POST /idea-inbox/{id}/promote`) — requires type + parent Feature, creates a Task or redirects to refinement of a new Feature.

### Phase 11 — Boards (Kanban + Sprint + Impact/Effort Matrix)
`GET /products/{id}/tasks?sprint_id=&project_id=&status=&task_type=`. Three views, same dnd-kit infrastructure:
- **Kanban**: columns = status
- **Sprint**: grouped by active sprint
- **Matrix**: Impact×Effort quadrants (on Feature, not Task), drag changes `impact`/`effort`

Project filter available on all three.

### Phase 12 — Next Up Queue
`GET /products/{id}/next-up` — tasks with all dependencies `done`, sorted by `position`. UI: dedicated screen/widget, the first thing visible when opening the platform.

### Phase 13 — Roadmap Timeline
Simple visualization (not a complex graph editor) — list/timeline of Epic/Feature with arrows from FeatureDependency. Read-only at first, editing later if it makes sense.

### Phase 14 — Command Palette
Global `Cmd+K` — quickly create a Task, navigate to any entity, simple full-text search (Postgres `ILIKE` or `tsvector`, no embeddings at first).

### Phase 15 — Onboarding
Pre-populated sample Product (example Epic/Feature/Task) generated on the app's first boot. Guided empty states on each main screen (Knowledge, Idea Inbox, Board).

### Phase 16 — Polish
Real incremental regeneration (delta, not full regeneration). Manual `outdated` marking + `superseded_by_task_id`. Bulk actions in Backlog (multi-select + status/sprint/type change). Saved filters. Simple in-app notifications (task unblocked, agent session processed).

---

## 6. UX notes (Jira-like)

- Fixed left sidebar: Product switcher, then Backlog / Board / Sprints / Knowledge / Idea Inbox / Roadmap
- Detail panel = side split-view, not a separate page
- Breadcrumb Product > Epic > Feature > Task visible in the panel
- Issue keys (`HAND-123`) shown everywhere a Task/Feature appears
- Colored badge + icon per `task_type`
- Progress bar on Feature/Epic ("3/7 tasks done")
- All boards (Kanban/Sprint/Matrix) reuse the same dnd-kit pattern

---

## 7. What we are NOT building (explicit scope exclusion from the MVP)

- RICE score / complex estimation sliders
- Automatic effort recalculation from Fibonacci complexity
- Interactive graph editor for dependencies
- Multi-user auth / roles (until it becomes necessary)
- Active vector search (pgvector prepared, but retrieval remains simple scope filtering at first)
- Email notifications
