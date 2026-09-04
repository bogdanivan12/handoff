-- ============================================================
-- AI-Native Product/Project Management Platform — Schema DDL
-- PostgreSQL 15+ (pgvector extension for future semantic retrieval)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector; -- pgvector, used later for embeddings

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE knowledge_type AS ENUM (
  'decision', 'convention', 'constraint',
  'domain_concept', 'technical_fact', 'known_issue'
);

CREATE TYPE knowledge_scope AS ENUM ('product', 'project');

CREATE TYPE knowledge_status AS ENUM (
  'draft',        -- proposed, pending review (e.g. from AgentSession)
  'active',
  'superseded',
  'conflicting',
  'rejected'
);

CREATE TYPE knowledge_provenance AS ENUM (
  'manual', 'extracted_from_task', 'extracted_from_agent_session'
);

CREATE TYPE knowledge_relation_type AS ENUM (
  'supersedes', 'conflicts_with', 'derived_from', 'refines'
);

CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done', 'outdated');

CREATE TYPE ac_format AS ENUM ('basic', 'gherkin');

CREATE TYPE draft_status AS ENUM ('pending_review', 'approved', 'rejected');

CREATE TYPE extraction_status AS ENUM ('pending', 'processed', 'failed');

CREATE TYPE proposed_completion_status AS ENUM ('done', 'partial', 'blocked');

CREATE TYPE severity AS ENUM ('hard', 'soft');

-- ============================================================
-- PRODUCT HIERARCHY
-- ============================================================

CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  acceptance_criteria_format_default ac_format NOT NULL DEFAULT 'basic',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE initiatives (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE epics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  initiative_id UUID NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- DELIVERY: PROJECT & SPRINT
-- ============================================================

CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sprints (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE, -- sprint is always at the Product level
  name TEXT NOT NULL,
  start_date DATE,
  end_date DATE,
  status TEXT NOT NULL DEFAULT 'planned', -- planned | active | completed
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- FEATURE (central unit of refinement + generation)
-- ============================================================

CREATE TABLE features (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  epic_id UUID NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
  default_project_id UUID REFERENCES projects(id) ON DELETE SET NULL, -- nullable, default only
  name TEXT NOT NULL,
  requirements TEXT, -- refinement content (could become JSONB later if more structure is needed)
  status TEXT NOT NULL DEFAULT 'draft', -- draft | ready | generating | generated
  acceptance_criteria_format ac_format NOT NULL DEFAULT 'basic',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_features_epic ON features(epic_id);
CREATE INDEX idx_features_default_project ON features(default_project_id);

-- ============================================================
-- KNOWLEDGE MODEL
-- ============================================================

CREATE TABLE knowledge_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  type knowledge_type NOT NULL,
  scope knowledge_scope NOT NULL,
  scope_ref_id UUID NOT NULL, -- product_id or project_id, depending on scope (validated at the app level)

  -- content structured per type; shape varies, validated at the app level (Pydantic)
  -- decision:        { subject, chosen, alternatives_considered[], rationale }
  -- convention:       { subject, rule, example? }
  -- constraint:       { subject, rule, rationale?, severity }
  -- domain_concept:   { term, definition, related_terms[] }
  -- technical_fact:   { subject, fact, verified_at }
  -- known_issue:      { subject, description, workaround?, status }
  content JSONB NOT NULL,

  confidence NUMERIC(3,2), -- 0.00–1.00, one-time, set manually or at extraction
  provenance knowledge_provenance NOT NULL DEFAULT 'manual',
  source_ref_type TEXT, -- 'task' | 'agent_session' | NULL (if manual)
  source_ref_id UUID,

  status knowledge_status NOT NULL DEFAULT 'active',

  embedding vector(1536), -- optional, for future semantic retrieval (pgvector)

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_scope ON knowledge_items(scope, scope_ref_id, status);
CREATE INDEX idx_knowledge_type ON knowledge_items(type);

CREATE TABLE knowledge_relations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  from_item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  to_item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  relation_type knowledge_relation_type NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_item_id != to_item_id)
);

CREATE INDEX idx_knowledge_relations_from ON knowledge_relations(from_item_id);
CREATE INDEX idx_knowledge_relations_to ON knowledge_relations(to_item_id);

-- ============================================================
-- TASK DRAFT (pre-approval) & TASK (real)
-- ============================================================

CREATE TABLE task_drafts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL, -- default = feature.default_project_id, editable

  title TEXT NOT NULL,
  context TEXT,
  scope TEXT,
  out_of_scope TEXT,

  status draft_status NOT NULL DEFAULT 'pending_review',

  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_drafts_feature ON task_drafts(feature_id, status);

CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  sprint_id UUID REFERENCES sprints(id) ON DELETE SET NULL,

  generated_from_draft_id UUID REFERENCES task_drafts(id) ON DELETE SET NULL,

  title TEXT NOT NULL,
  status task_status NOT NULL DEFAULT 'todo',
  outdated_reason TEXT,
  superseded_by_task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,

  context TEXT,
  scope TEXT,
  out_of_scope TEXT,

  -- snapshot of the KnowledgeItems relevant at generation time (not a live reference)
  relevant_knowledge JSONB NOT NULL DEFAULT '[]',
  -- e.g. [{ "knowledge_item_id": "...", "type": "constraint", "content": {...} }, ...]
  -- knowledge_item_id kept only for traceability, not for live lookup

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_feature ON tasks(feature_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_sprint ON tasks(sprint_id);
CREATE INDEX idx_tasks_status ON tasks(status);

-- ============================================================
-- ACCEPTANCE CRITERIA (on TaskDraft AND on Task)
-- ============================================================

CREATE TABLE acceptance_criteria (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  task_draft_id UUID REFERENCES task_drafts(id) ON DELETE CASCADE,
  task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
  CHECK (
    (task_draft_id IS NOT NULL AND task_id IS NULL) OR
    (task_draft_id IS NULL AND task_id IS NOT NULL)
  ), -- belongs to exactly one of the two

  format ac_format NOT NULL DEFAULT 'basic',

  description TEXT, -- used when format = basic
  given TEXT,        -- used when format = gherkin
  when_ TEXT,
  then_ TEXT,

  position INTEGER NOT NULL DEFAULT 0, -- display order

  checked BOOLEAN NOT NULL DEFAULT false,
  checked_at TIMESTAMPTZ,
  checked_by UUID, -- FK to users, if/when multi-user auth is added
  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ac_task_draft ON acceptance_criteria(task_draft_id);
CREATE INDEX idx_ac_task ON acceptance_criteria(task_id);

-- ============================================================
-- GENERATED PROMPT (on-demand projection, not the source of truth)
-- ============================================================

CREATE TABLE generated_prompts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  is_stale BOOLEAN NOT NULL DEFAULT false,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_generated_prompts_task ON generated_prompts(task_id);

-- ============================================================
-- AGENT SESSION (uploaded external AI agent conversation)
-- ============================================================

CREATE TABLE agent_sessions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,

  raw_content TEXT NOT NULL, -- the uploaded conversation, raw

  extraction_status extraction_status NOT NULL DEFAULT 'pending',
  extracted_summary TEXT,
  proposed_completion_status proposed_completion_status,

  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_agent_sessions_task ON agent_sessions(task_id);

-- knowledge_items proposed from an AgentSession are normal rows in
-- knowledge_items with: provenance = 'extracted_from_agent_session',
-- source_ref_type = 'agent_session', source_ref_id = agent_sessions.id,
-- status = 'draft' until the user reviews it (and also picks the final scope).

-- ============================================================
-- TRIGGERS: updated_at auto-refresh (common pattern, optional)
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_initiatives_updated_at BEFORE UPDATE ON initiatives
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_epics_updated_at BEFORE UPDATE ON epics
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_features_updated_at BEFORE UPDATE ON features
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_sprints_updated_at BEFORE UPDATE ON sprints
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_knowledge_items_updated_at BEFORE UPDATE ON knowledge_items
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
