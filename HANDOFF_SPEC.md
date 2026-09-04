# Handoff — Spec de proiect

Platformă de product & project management, product-centric, gândită pentru era dezvoltării asistate de AI. Nu execută task-uri — le pregătește, structurat, gata de dat unui agent AI de coding (Claude Code, Cursor, etc.), și acumulează memorie de proiect (facts) care informează generarea viitoare de task-uri.

Acest document e sursa de adevăr pentru implementare. Urmează fazele în ordine — fiecare fază produce o felie verticală funcțională (DB → API → UI), testabilă înainte să treci mai departe.

---

## 1. Principii de design

- **Human-in-the-loop peste tot** — nimic generat de AI (task-uri, facts, changelog) nu devine "activ" fără aprobare explicită a userului.
- **Simplitate peste completitudine** — preferăm un concept simplu, ușor de folosit, unui framework "corect" dar greoi (ex: matrice Impact/Effort în loc de scor RICE).
- **Product-centric** — orice unitate de lucru (feature, bug, improvement, chore, research) se leagă înapoi la o Feature. Nimic nu "plutește" fără context de business.
- **Jira-like vizual și funcțional** — sidebar fix, issue keys (`HAND-123`), panel de detaliu split-view, board-uri drag-and-drop, badge-uri colorate per tip.
- **Snapshot, nu referință live** — orice context dat unui AI la generare (knowledge, prompt) se salvează ca snapshot imutabil, nu recalculat retroactiv.

---

## 2. Tech stack

- **Backend**: Python + FastAPI, SQLAlchemy 2.0 async (sau SQLModel), Alembic pentru migrations
- **DB**: PostgreSQL 15+ cu extensia `pgvector` (pregătită pentru retrieval semantic ulterior, neutilizată activ în MVP)
- **Frontend**: React + TypeScript + Vite, Tailwind CSS + shadcn/ui, `dnd-kit` pentru drag-and-drop (board-uri)
- **AI**: LiteLLM (proxy deja deployat de user) — toate apelurile AI se fac către endpoint-ul LiteLLM configurat, format OpenAI-compatible (`/v1/chat/completions`)
- **Infra**: Docker + docker-compose local; deploy țintă pe k3s (homelab, Proxmox)
- **Auth**: niciuna în MVP (single-user). Se adaugă ulterior dacă devine multi-user.

---

## 3. Glosar de concepte

| Concept | Descriere |
|---|---|
| **Product** | Ce se construiește. Rădăcina ierarhiei. |
| **Initiative** | Obiectiv strategic sub un Product. |
| **Epic** | Arie majoră de produs, sub o Initiative. |
| **Feature** | Unitate centrală de refinement. Sub un Epic. Toate Task-urile se leagă la o Feature. |
| **Project** | Concept de delivery, separat de ierarhia de produs. O Feature poate produce Task-uri pentru mai multe Project-uri. |
| **Sprint** | Mereu la nivel de Product (nu Project). Board-urile se filtrează opțional per Project. |
| **Task** | Cea mai mică unitate de lucru, gândită să fie dată unui agent AI. Leagă Feature + Project + Sprint (opțional). |
| **TaskDraft** | Task propus de AI, în așteptare de review/aprobare, înainte să devină Task real. |
| **KnowledgeItem** | Fact tipizat (decision/convention/constraint/domain_concept/technical_fact/known_issue), scoped la Product sau Project. |
| **AgentSession** | Conversație uploadată (user ↔ agent AI extern), din care se extrag completion status + facts noi propuse. |
| **Idea Inbox** | Punct unic de captură pentru orice idee/bug/improvement brut, înainte de organizare formală. |
| **Next Up Queue** | Vedere calculată: task-uri fără dependențe nerezolvate, gata de trimis unui agent AI. |

---

## 4. Model de date

Schema SQL de bază există deja (vezi `schema.sql` — Product, Initiative, Epic, Feature, Project, Sprint, KnowledgeItem, KnowledgeRelation, TaskDraft, Task, AcceptanceCriterion, GeneratedPrompt, AgentSession). Adaugă următoarele, decise ulterior:

### 4.1 Task — câmpuri noi

```
Task
  ...(câmpuri existente)
  task_type: feature | bug | improvement | chore | research   -- discriminator
  feature_id NOT NULL   -- rămâne obligatoriu indiferent de task_type
  impact: low | high     -- nullable, folosit doar pt Feature de fapt — vezi 4.3
  position INTEGER        -- ordine în backlog/coloană, folosit ca "prioritate" implicită
```

Notă: `task_type` influențează:
- template-ul `GeneratedPrompt` (ex: `research` cere output de tip concluzie/raport, nu cod)
- culoare/iconiță pe board-uri (bug=roșu, feature=albastru, improvement=verde, chore=gri, research=violet)
- filtrare în Backlog/Board

### 4.2 TaskDependency

```
TaskDependency
  id UUID PK
  task_id UUID FK → tasks
  depends_on_task_id UUID FK → tasks
  created_at
  CHECK (task_id != depends_on_task_id)
```

Un task e "eligibil" pentru Next Up Queue doar dacă toate `depends_on_task_id` au `status = done`.

### 4.3 Feature — câmpuri noi

```
Feature
  ...(câmpuri existente)
  impact: low | high        -- nullable
  effort: low | high        -- nullable
  priority: low | medium | high | critical   -- nullable, override manual
  success_looks_like TEXT   -- opțional, o propoziție de succes (nu OKR framework complet)
```

Cadranul matricei (Quick Win / Big Bet / Fill-in / Time Sink) se calculează la afișare din `impact`+`effort`, nu se stochează.

### 4.4 FeatureDependency

```
FeatureDependency
  id UUID PK
  feature_id UUID FK → features
  depends_on_feature_id UUID FK → features
  created_at
  CHECK (feature_id != depends_on_feature_id)
```

Folosit pentru roadmap timeline (săgeți între Feature-uri).

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

Flux: user scrie idee brută → rămâne `new` → la promovare, alege tip + Feature părinte (obligatoriu) → devine Task real (dacă tip ≠ feature) sau Feature nouă în refinement (dacă tip = feature).

### 4.6 Tags (simplu, opțional)

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

La generarea unui Task, AI-ul poate sugera 1-3 tag-uri (nu creează automat, doar propune — user acceptă/respinge la review-ul TaskDraft-ului).

### 4.7 Issue key

```
Product
  ...
  key_prefix TEXT NOT NULL  -- ex: "HAND", configurabil la creare Product

Feature / Task
  ...
  issue_number INTEGER  -- secvențial per Product, generat la creare
  -- afișat ca "{product.key_prefix}-{issue_number}", ex: HAND-123
```

Secvența poate fi comună între Feature și Task (un singur counter per Product) sau separată — recomandat: **un singur counter per Product**, mai simplu de implementat (o coloană `SERIAL` sau secvență Postgres per Product), și mai natural pentru referențiere (nu contează dacă HAND-45 e Feature sau Task).

---

## 5. Faze de dezvoltare

Fiecare fază = felie verticală completă (model → endpoint → UI), testabilă înainte de a trece mai departe. Nu sări la generare AI (Faza 6) înainte ca 0-5 să fie solide.

### Faza 0 — Scaffolding
Repo `/backend` (FastAPI), `/frontend` (React+Vite), `/infra` (docker-compose). Backend cu SQLAlchemy async + Alembic conectat la Postgres. Frontend Vite+React+TS+Tailwind+shadcn cu un ecran de test (`/health`). `docker-compose up` pornește tot.

### Faza 1 — Product Hierarchy + Issue Keys
CRUD Product/Initiative/Epic/Feature conform schema. Adaugă `key_prefix` pe Product și `issue_number` auto-generat (secvență per Product) pe Feature. UI: navigare ierarhică simplă + breadcrumb.

### Faza 2 — Project & Sprint
CRUD Project (legat de Product) și Sprint (legat de Product, cu date + status). UI: management ecran per Product.

### Faza 3 — Knowledge Model
CRUD KnowledgeItem cu Pydantic discriminated union per `type` (6 tipuri, shape-uri din schema.sql). CRUD KnowledgeRelation (`supersedes`/`conflicts_with`). UI: listă filtrabilă pe scope, formular dinamic per tip.

### Faza 4 — Task de bază (manual, fără AI)
CRUD Task (`feature_id` obligatoriu, `task_type` enum, `issue_number` din același counter ca Feature) + AcceptanceCriterion (toggle basic/gherkin). UI: panel de detaliu split-view (click pe task deschide lateral, nu navighezi la altă pagină).

### Faza 5 — Dependencies
CRUD TaskDependency + FeatureDependency. Endpoint `GET /tasks/{id}/is-blocked` (verifică dacă toate dependențele au status=done). UI: afișare vizuală (lacăt/gri pe task-uri blocate în board).

### Faza 6 — Generare AI: Feature → TaskDraft
Endpoint `POST /features/{id}/generate-tasks`: colectează requirements + knowledge (product+project scope) + task-uri existente (dacă regenerare) → prompt către LiteLLM → parsare JSON strict → creează `task_drafts` + `acceptance_criteria`. AI sugerează și `task_type` + tag-uri per draft.

### Faza 7 — Review & Approval
Editare TaskDraft înainte de aprobare. `POST /task-drafts/{id}/approve` → creează Task real, migrează acceptance criteria, construiește `relevant_knowledge` snapshot. `POST /task-drafts/{id}/reject`. UI: ecran de review cu diff vizual dacă e regenerare (task nou vs. task devenit outdated).

### Faza 8 — Generated Prompt
`GET /tasks/{id}/is-ready`, `POST /tasks/{id}/generate-prompt` (template variază ușor per `task_type`). `is_stale=true` automat la orice edit ulterior. UI: buton disabled cu tooltip dacă nu e ready.

### Faza 9 — Agent Session upload & extraction
Upload text/markdown → apel LiteLLM pentru extracție (summary, completion status, facts propuse) → facts ca `knowledge_items` cu `status=draft` → review + alegere scope obligatorie la aprobare.

### Faza 10 — Idea Inbox
CRUD IdeaInboxItem. Endpoint de promovare (`POST /idea-inbox/{id}/promote`) — cere tip + Feature părinte, creează Task sau redirecționează spre refinement de Feature nouă.

### Faza 11 — Boards (Kanban + Sprint + Impact/Effort Matrix)
`GET /products/{id}/tasks?sprint_id=&project_id=&status=&task_type=`. Trei view-uri, aceeași infrastructură dnd-kit:
- **Kanban**: coloane = status
- **Sprint**: grupare pe sprint activ
- **Matrice**: cadrane Impact×Effort (pe Feature, nu Task), drag schimbă `impact`/`effort`

Filtru Project disponibil pe toate trei.

### Faza 12 — Next Up Queue
`GET /products/{id}/next-up` — task-uri cu toate dependențele `done`, sortate după `position`. UI: ecran/widget dedicat, primul lucru vizibil la deschiderea platformei.

### Faza 13 — Roadmap Timeline
Vizualizare simplă (nu graph editor complex) — listă/axă de timp cu Epic/Feature și săgeți din FeatureDependency. Read-only la început, editare ulterioară dacă are sens.

### Faza 14 — Command Palette
`Cmd+K` global — creează Task rapid, navighează la orice entitate, căutare full-text simplă (Postgres `ILIKE` sau `tsvector`, nu embeddings la început).

### Faza 15 — Onboarding
Sample Product pre-populat (Epic/Feature/Task exemplu) generat la primul boot al aplicației. Empty states ghidate pe fiecare ecran principal (Knowledge, Idea Inbox, Board).

### Faza 16 — Polish
Regenerare incrementală reală (delta, nu regenerare completă). Marcare manuală `outdated` + `superseded_by_task_id`. Bulk actions în Backlog (multi-select + schimbare status/sprint/tip). Saved filters. Notificări in-app simple (task deblocat, agent session procesată).

---

## 6. Note UX (Jira-like)

- Sidebar fix stânga: Product switcher, apoi Backlog / Board / Sprints / Knowledge / Idea Inbox / Roadmap
- Panel de detaliu = split-view lateral, nu pagină separată
- Breadcrumb Product > Epic > Feature > Task vizibil în panel
- Issue keys (`HAND-123`) afișate peste tot unde apare Task/Feature
- Badge colorat + iconiță per `task_type`
- Progress bar pe Feature/Epic ("3/7 tasks done")
- Toate board-urile (Kanban/Sprint/Matrix) reutilizează același pattern dnd-kit

---

## 7. Ce NU construim (scop explicit exclus din MVP)

- Scor RICE / sliders complexe de estimare
- Recalcul automat de effort din complexitate Fibonacci
- Graph editor interactiv pentru dependențe
- Auth multi-user / roluri (până nu devine necesar)
- Vector search activ (pgvector pregătit, dar retrieval rămâne filtrare simplă pe scope la început)
- Notificări email
