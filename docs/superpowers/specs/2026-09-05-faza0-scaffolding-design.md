# Faza 0 — Scaffolding — Design

Sub-proiect din [HANDOFF_SPEC.md](../../../HANDOFF_SPEC.md), Faza 0. Prima felie verticală
a platformei Handoff: infrastructură de bază (backend + frontend + docker-compose),
fără logică de business încă. Scop: `docker-compose up` pornește tot, `/health`
confirmă conectivitate reală la DB.

## Context

Repo gol la momentul acestui spec (doar `README.md`). Tech stack fixat în
`HANDOFF_SPEC.md` §2: Python/FastAPI, SQLAlchemy 2.0 async, Alembic, Postgres 15+
cu `pgvector`, React/TS/Vite/Tailwind/shadcn, docker-compose local, deploy țintă
k3s (homelab, Proxmox).

Decizie importantă (diferă de presupunerea implicită din spec-ul general):
**Postgres nu rulează local în docker-compose.** Userul are deja o instanță
Postgres pe homelab-ul k3s; backend-ul se conectează direct la ea, și pentru
dev local, și pentru deploy. `pgvector` e presupus deja instalat acolo —
nu e responsabilitatea acestei faze.

## Layout

```
/backend   FastAPI + SQLAlchemy 2.0 async + Alembic
/frontend  Vite + React + TS + Tailwind + shadcn/ui
/infra     docker-compose (backend + frontend; fără Postgres)
```

## Backend

- Python 3.12, `uv` ca package manager (lockfile, cache rapid în Docker layers)
- Driver `asyncpg`, SQLAlchemy 2.0 async engine
- `pydantic-settings` citește `DATABASE_URL` din environment (`.env` local,
  necommitted; `.env.example` cu placeholder)
- Alembic configurat pentru async (env.py adaptat), migrare **baseline goală**
  — nu creează niciun tabel. Scopul migrării inițiale e doar să confirme că
  Alembic poate vorbi cu DB-ul. Tabelele din `schema.sql` + câmpurile noi din
  spec vin incremental, câte o felie per fază (Faza 1 = Product/Initiative/
  Epic/Feature, etc.) — nu toate deodată.
- `GET /health` → `{"status": "ok", "db": "connected"}` sau
  `{"status": "error", "db": "error"}` (HTTP 200 vs 503). Rulează `SELECT 1`
  pe conexiune la fiecare apel (nu cached) ca să reflecte starea reală.
- CORS middleware activ, origin permis = `http://localhost:5173` (Vite dev
  server), configurabil prin env pentru alte origini ulterior.

## Frontend

- Vite + React + TypeScript, Tailwind CSS, shadcn/ui inițializat (componente
  de bază instalate: `button`, `card` — suficient pentru ecranul de test)
- npm ca package manager
- Ecran de test la `/`: la load, apelează `GET {VITE_API_URL}/health`,
  afișează un card cu status vizual (verde = ok, roșu = error/unreachable)
- `VITE_API_URL` configurabil prin env (`.env.example` cu default
  `http://localhost:8000`)

## Infra (docker-compose)

- `infra/docker-compose.yml`, două servicii:
  - `backend`: build din `/backend/Dockerfile`, uvicorn cu `--reload`, volume
    mount pe cod sursă pentru hot-reload, `env_file: ../backend/.env`
  - `frontend`: build din `/frontend/Dockerfile`, `npm run dev -- --host`,
    volume mount pe cod sursă, `env_file: ../frontend/.env`
- Fără serviciu `postgres` — conexiunea la homelab se face prin
  `DATABASE_URL` din `.env`-ul backend-ului (rețeaua LAN/VPN a userului
  trebuie să permită accesul; asta e responsabilitatea userului, nu e
  scriptat aici)
- `docker-compose up` din `/infra` pornește ambele servicii

## Testing

- Backend: pytest, un test pentru `/health` cu conexiunea DB mockuită (nu
  depinde de accesul live la homelab — testul verifică ambele ramuri:
  conexiune ok și conexiune care aruncă excepție)
- Frontend: verificare manuală vizuală a ecranului de test (fără suite
  automată în această fază — YAGNI, nu există încă logică de testat)

## Ce nu construim în Faza 0

- Niciun tabel de business (Product, Feature, Task etc.) — vine per fază,
  începând cu Faza 1
- Niciun manifest k3s de deploy (rămâne pentru o fază ulterioară / decizie
  separată)
- Autentificare (explicit exclusă din MVP per §7 din spec-ul general)

## Riscuri / presupuneri deschise

- Homelab Postgres are deja extensia `pgvector` instalată — nu verificăm,
  nu instalăm
- Mediul de dev local poate ajunge în rețea la homelab k3s (LAN/VPN) — dacă
  nu, `/health` va raporta `db: error`, ceea ce e comportamentul corect de
  semnalare, nu un bug de rezolvat în această fază
