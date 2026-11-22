# 01 — Architecture, Repo Layout & Conventions

**Names:** product, repo and root folder are **Tartib**. Hostnames: web `tartib.vercel.app`,
API `tartib-api.duckdns.org`. The Python package stays `scheduler` (internal; never shown to users).

## 1. System shape

```
  Phone PWA ─┐
  Browser   ─┴─► Vercel (free): Next.js web app  https://tartib.vercel.app
                  └─ rewrites /api/* ───────────────┐   (same-origin for the browser, D-02)
  Google push webhooks ─────────────────────────────┤
  Agents (Bearer token) ────────────────────────────┤
             ┌───────────── VPS (Docker Compose, total mem cap ≈ 1 GB) ─────────────┐
             │ caddy (TLS for API_HOST, /api → api:8000)                   48 MB   │
             │   │                                                                │
             │   ▼                                                                │
 (Bearer)    │ api   FastAPI + uvicorn (1 worker)  ── reads/writes ──► db         │
             │       • HTTP only, never runs schedules                 384 MB     │
             │       • enqueues jobs into `job` table                             │
             │ worker  python -m scheduler.worker                       256 MB    │
             │       • APScheduler (hourly plan, sync, nightly rollover, …)       │
             │       • polls `job` table every 1 s (D-29)                         │
             │       • Google Calendar / Notion / Push / Discord I/O              │
             │ db    Postgres 19                                        320 MB    │
             │ bot   (optional profile) discord.py shim → api           64 MB     │
             └────────────────────────────────────────────────────────────────────┘
                          │                         │
                Google Calendar API           Notion API · Web Push · Discord webhook
```

**Data flow of a re-plan (the "trust loop").**
`trigger` (any change within ~2 s — D-29 — or hourly safety net / calendar push / manual) → worker builds an **engine
input snapshot** from Postgres → **pure engine** returns planned blocks + log → **diff** against
current placements → **classify** each change → store as the single `proposed` plan run →
auto-apply safe changes if enabled → notify → user accepts → **apply** writes Google Calendar
(retry once, roll back on failure) → DB placements updated in one transaction → engine log +
activity written → Notion mirror job enqueued.

## 2. Tech stack (pin exact versions in lockfiles at init time)

### Backend (`backend/`)
| Concern | Choice | Notes |
|---|---|---|
| Language | **Python 3.15** | all compiled deps ship 3.15 wheels (checked 2026-11-22) |
| Package/env manager | **uv** | `uv sync`, `uv run …`; lockfile `uv.lock` committed |
| Web framework | **FastAPI** + **uvicorn** | sync endpoints (`def`, not `async def`) — simpler, single user |
| ORM | **SQLAlchemy 2.1** (typed `Mapped[]` style), **psycopg 3.3** driver | sync sessions |
| Migrations | **Alembic** | one migration per package that changes schema |
| Validation | **Pydantic v2**, **pydantic-settings** | |
| Scheduling | **APScheduler 3.11** `BlockingScheduler` | worker only; pin `<4` — 4.0 is still pre-release (D-30) |
| HTTP client | **httpx** | |
| Google | `google-auth`, `google-auth-oauthlib`, `google-api-python-client` | |
| Notion | `notion-client` | |
| Prayer times | `adhanpy` + in-house NOAA cross-check | see `05-integrations.md` |
| Passkeys | `webauthn` (py_webauthn) | |
| Push | `pywebpush` | VAPID |
| Crypto | `cryptography` (Fernet) | encrypt tokens at rest |
| Tests | `pytest`, `hypothesis`, `pytest-cov`, `freezegun`/`time-machine` | |
| Lint/type | `ruff` (lint + format), `mypy --strict` on `engine/` | |

### Frontend (`web/`)
| Concern | Choice |
|---|---|
| Runtime / pkg mgr | **Node 26 LTS**, **pnpm 10** (via corepack) |
| Framework | **Next.js 16 (App Router, Turbopack)**, deployed on **Vercel** (D-02); screens are client components |
| UI | **React 19**, **TypeScript 5 strict** |
| Styling | **Tailwind CSS 4.3** with CSS variables from `web/src/design/tokens.css` |
| Primitives | **Radix UI** (dialog, popover, dropdown, tabs, switch, tooltip, toast-less) |
| Routing | Next.js App Router (file-based, `web/src/app/`) |
| Server state | **TanStack Query v5** |
| Client state | **Zustand** (UI only: sheet open, palette open, selected filters) |
| Forms | **react-hook-form** + **zod** |
| Dates | **date-fns** + **@date-fns/tz** (`TZDate`) — always render in settings tz |
| Drag | **@dnd-kit/core** |
| Command palette | **cmdk** |
| Toasts | **sonner** |
| Charts | **Recharts** |
| API types | **openapi-typescript** → `web/src/api/schema.d.ts`; **openapi-fetch** client |
| PWA | **Serwist** (`@serwist/next`), custom SW `src/app/sw.ts`, manifest `src/app/manifest.ts` |
| Offline store | **idb-keyval** (outbox) + TanStack Query persister |
| Tests | **Vitest** + Testing Library, **Playwright** (e2e, mobile + desktop projects), **MSW** for mocks |

### Version policy (D-30)
- Use the **latest stable** release of every runtime and library at the time a package is
  implemented, and pin exact versions in `uv.lock` / `pnpm-lock.yaml`. Never use pre-releases
  (alpha, beta, rc). The one listed exception is APScheduler, which stays on 3.x until 4.0 is stable.
- Baseline checked on 2026-11-22: Python 3.15 · PostgreSQL 19 · Node 26 LTS · Next.js 16.4 ·
  React 19.3 · Tailwind 4.3 · TanStack Query 5 · SQLAlchemy 2.1 · FastAPI 0.165 · Pydantic 2 ·
  psycopg 3.3 · APScheduler 3.11.
- If a dependency has no wheel for the current Python, don't downgrade the whole project
  silently. Record a `PROPOSED` decision, and only then fall back one minor version (e.g. 3.14).
- **Renovate** (or Dependabot) opens weekly grouped update PRs; CI must pass before merging.
  Major version bumps get their own PR, with a note in `docs/decisions.md`.

### Infra
Docker Compose v2, **Caddy 2**, **Postgres 19**, DuckDNS hostname, Healthchecks.io (free) for
the external dead-man switch, Discord webhook for alerts.

## 3. Repository layout (target)

```
Tartib/
├── AGENTS.md                    rules for coding agents (read first)
├── README.md
├── Makefile                     one entry point: make dev | test | check | gen-api | …
├── .env.example
├── .editorconfig  .gitignore
├── docs/
│   ├── 01-requirements.md 02-engine-spec.md 03-build-analysis.md 04-deployment.md
│   ├── decisions.md
│   └── plans/                   ← these files
├── mockups/                     visual intent (read-only)
├── backend/
│   ├── pyproject.toml  uv.lock  alembic.ini
│   ├── migrations/              alembic env + versions/
│   ├── src/scheduler/
│   │   ├── __init__.py
│   │   ├── config.py            env settings (pydantic-settings)
│   │   ├── db.py                engine, SessionLocal, session_scope()
│   │   ├── clock.py             now() — the ONLY place that reads wall time
│   │   ├── constants.py         technical (non-scheduling) timeouts only
│   │   ├── models/              SQLAlchemy ORM, one module per aggregate
│   │   ├── schemas/             Pydantic request/response DTOs, one module per router
│   │   ├── engine/              PURE scheduling engine (see 03-engine.md) — no I/O
│   │   ├── services/            business logic; the only layer that touches both DB and engine
│   │   ├── integrations/        google/, notion/, prayer_times.py, push.py, llm.py, email.py, discord.py, healthcheck.py
│   │   ├── auth/                sessions.py, magic_link.py, passkey.py, agent_tokens.py, scopes.py
│   │   ├── api/                 app.py, deps.py, errors.py, routers/*.py
│   │   ├── worker/              __main__.py, queue.py, jobs.py, schedules.py
│   │   ├── seed/                defaults.py (settings + vocab defaults), seeder.py
│   │   └── cli.py               `scheduler-cli` (login-link, seed, run-plan, export-settings)
│   └── tests/
│       ├── conftest.py
│       ├── engine/              pure unit + acceptance + property tests (no DB)
│       ├── services/            DB-backed tests (real Postgres via docker)
│       ├── api/                 TestClient tests
│       └── fixtures/            builders: make_task(), make_habit(), make_day()…
├── web/
│   ├── package.json  pnpm-lock.yaml  next.config.ts  tsconfig.json  vitest.config.ts
│   ├── public/                  icons
│   ├── src/
│   │   ├── app/                 App Router: layout.tsx, providers.tsx, manifest.ts, sw.ts,
│   │   │                        (auth)/login, (app)/today|week|tasks|…/page.tsx, (app)/layout.tsx (shell)
│   │   ├── shell/               DesktopShell, MobileShell, Rail, TabBar, Header, PrecedenceRail
│   │   ├── api/                 schema.d.ts (generated), client.ts, keys.ts, hooks/
│   │   ├── design/              tokens.css, components/ (Button, Chip, Badge, Sheet, …)
│   │   ├── features/            today/ week/ tasks/ habits/ prayers/ insights/ log/
│   │   │                        plan-review/ decisions/ capture/ settings/ agent/ auth/ onboarding/
│   │   ├── lib/                 time.ts, format.ts, duration.ts, offline/outbox.ts, undo.ts
│   └── e2e/                     Playwright specs
├── bot/                         optional Discord shim (own pyproject)
└── deploy/
    ├── docker-compose.yml       production
    ├── docker-compose.dev.yml   local: db only (+ mailpit)
    ├── backend.Dockerfile
    ├── caddy/Caddyfile          API-only reverse proxy (web is on Vercel)
    └── scripts/                 bootstrap-vps.sh, deploy.sh, backup.sh, restore.sh
```

### Layering rules (enforced by a test — see F-02)

```
api/routers  →  services  →  engine (pure)
                   │
                   ├──→ models / db
                   └──→ integrations
worker/jobs  →  services
```

- `engine/` imports **only** these stdlib modules: `__future__`, `datetime`, `zoneinfo`,
  `dataclasses`, `enum`, `uuid`, `hashlib`, `itertools`, `functools`, `collections`, `heapq`,
  `bisect`, `math`, `typing` (plus `scheduler.engine.*`). No SQLAlchemy, no Pydantic, no httpx,
  no `datetime.now()`.
- `api/routers/*` never import `models` or `integrations` directly. They call services.
- `services/*` never import from `api/`.
- Only `clock.py` calls `datetime.now()`. Everything else takes `now` as a parameter or calls
  `clock.now()`. Tests freeze it with `clock.set_fixed(...)`.

## 4. Conventions (all code)

### Time
- DB columns: `timestamptz` for instants (stored UTC), `date` for local days, `time` for
  times-of-day, `integer` minutes for durations (suffix `_min`).
- Conversion to local time uses the tz from settings (`settings.general.timezone`, default
  `Asia/Kolkata`). The engine receives tz-aware datetimes only. **Naive datetimes are a bug**: add
  `assert dt.tzinfo is not None` in engine constructors.
- Slot granularity is `block_rules.slot_granularity_min` (default 5). All engine-produced
  starts/ends are multiples of it (in local time).
- API: ISO-8601 with offset (`2026-11-22T13:20:00+05:30`). Dates `YYYY-MM-DD`. Durations
  as integer minutes.

### Naming
- Python: `snake_case`; enum values are lowercase strings (`"scheduled"`), stored as Postgres
  `text` with a `CHECK` constraint (not native PG enums — easier migrations).
- JSON over the wire: `snake_case` keys (no camelCase conversion; the TS types are generated).
- Rule codes: `SCREAMING_SNAKE`, defined once in `engine/rules.py`.

### Errors (API)
```json
{ "error": { "code": "TASK_NOT_FOUND", "message": "Task 3f… does not exist", "details": {} } }
```
HTTP: 400 validation (`VALIDATION_ERROR`, details = pydantic errors) · 401 `UNAUTHENTICATED` ·
403 `FORBIDDEN_SCOPE` · 404 `*_NOT_FOUND` · 409 `CONFLICT_*` · 422 `UNPROCESSABLE_*` (domain
rule rejection) · 429 `RATE_LIMITED` · 502 `UPSTREAM_GOOGLE` / `UPSTREAM_NOTION`.

### Attribution (AGT-6)
Every mutating service function takes an `ActorContext(actor: str, auto_approved: bool,
token_id: UUID | None)` as its first argument. It is resolved once in `api/deps.py`. Services
write it to the record's `*_by` / `*_auto_approved` columns and to `activity`.

### Settings access (SET-0)
Services read settings through `services/settings.py::get_settings(session) -> AppSettings`
(a Pydantic model assembled from the `app_setting` rows + vocab). **Grep rule:** no numeric
literal for minutes, times or thresholds may appear in `engine/` or `services/` except in
`seed/defaults.py` and tests. CI runs `scripts/check_no_magic_numbers.py` (F-02).

### Logging
JSON lines to stdout (`logging` + a small JSON formatter). Each line: `ts, level, logger, msg,
request_id?, job_id?, plan_run_id?`. Never log tokens, codes or the encryption key.

## 5. Environment variables (`.env.example`)

| Var | Required | Example / default | Used by |
|---|---|---|---|
| `APP_ENV` | yes | `dev` \| `prod` \| `test` | all |
| `APP_BASE_URL` | yes | `https://tartib.vercel.app` (dev `http://localhost:3000`) | OAuth redirect default, links, passkey RP origin |
| `APP_ENCRYPTION_KEY` | yes | Fernet key (`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`) | crypto |
| `APP_SESSION_SECRET` | yes | 64 random hex chars | session token HMAC |
| `DATABASE_URL` | yes | `postgresql+psycopg://tartib:***@db:5432/tartib` | api, worker |
| `OWNER_EMAIL` | yes | the single user's email | auth |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | no (can be set in UI) | | IN-02 |
| `NOTION_TOKEN` | no (UI) | | IN-08 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | no (UI) | `https://api.deepseek.com` / `deepseek-chat` | IN-12 |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | no (generated on first boot if absent, stored encrypted) | `mailto:owner@example.com` | IN-10 |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | no | | IN-13 |
| `DISCORD_ALERT_WEBHOOK_URL` | no (UI) | | IN-11 |
| `HEALTHCHECK_PING_URL` | no (UI) | `https://hc-ping.com/<uuid>` | WK-05 |
| `FAKE_GOOGLE` | no | `1` in dev/test → in-memory calendar | IN-04 |
| `POSTGRES_PASSWORD` | yes (compose) | | db |
| `API_HOST` | yes (prod compose) | `tartib-api.duckdns.org` | Caddy site address for the API |
| `API_PUBLIC_URL` | yes (prod) | `https://tartib-api.duckdns.org` | Google push webhook address (D-29) |
| `API_ORIGIN` | **Vercel** env (web) | `https://tartib-api.duckdns.org` | target of the `/api` rewrite |
| `TEST_DATABASE_URL` | tests | `postgresql+psycopg://tartib:tartib@localhost:5433/tartib_test` | pytest |

## 6. Foundation work packages

### F-01 — Repo hygiene & Makefile
**Depends on:** —  **Size:** S
**Files:** `.gitignore`, `.editorconfig`, `Makefile`, `README.md` (dev section), `.env.example`
**Steps:**
1. `git init` if not a repo. Ensure `.gitignore` covers `.env`, `__pycache__/`, `.venv/`,
   `node_modules/`, `web/.next/`, `.pytest_cache/`, `.DS_Store`, `*.log`, `playwright-report/`.
2. Makefile targets (each must work from repo root):
   `dev-db` (compose dev up), `dev-api` (`cd backend && uv run uvicorn scheduler.api.app:app --reload`),
   `dev-worker`, `dev-web` (`cd web && pnpm dev` → Next on :3000, rewrites /api to :8000), `migrate`, `seed`, `test` (backend + web unit),
   `test-e2e`, `lint`, `typecheck`, `check` (= lint + typecheck + test), `gen-api`
   (dump OpenAPI from app → `web/src/api/openapi.json` → `pnpm openapi-typescript`).
**Done when:** `make help` lists targets; `.env.example` contains every var in §5.

### F-02 — Backend skeleton & architecture guards
**Depends on:** F-01  **Size:** M
**Files:** `backend/pyproject.toml`, `backend/src/scheduler/{__init__,config,db,clock}.py`,
`backend/src/scheduler/api/app.py` (health route only), `backend/tests/test_architecture.py`,
`backend/scripts/check_no_magic_numbers.py`
**Steps:**
1. `uv init --package backend` style layout with `src/scheduler`; `requires-python = ">=3.15"`, `.python-version` = `3.15`; add deps from §2.
   Console script: `scheduler-cli = "scheduler.cli:main"`.
2. `config.py`: `class Env(BaseSettings)` with every var in §5; `get_env()` cached.
3. `clock.py`: `now() -> datetime` (UTC, tz-aware); `set_fixed(dt)` / `reset()` for tests.
4. `db.py`: `engine = create_engine(DATABASE_URL, pool_size=5, pool_pre_ping=True)`,
   `SessionLocal`, context manager `session_scope()` (commit/rollback).
5. `api/app.py`: FastAPI app, `GET /api/health → {"status":"ok"}`.
6. `test_architecture.py`: walk `src/scheduler/engine/**.py`, parse imports with `ast`, fail on any
   import outside the stdlib allow-list in §3; fail if `datetime.now`/`date.today`/`time.time`
   appears outside `clock.py`; fail if `api/routers` imports `scheduler.models` or
   `scheduler.integrations`.
7. `check_no_magic_numbers.py`: scan `engine/` and `services/` for integer literals used in
   `timedelta(...)`, `time(...)`, or assigned to names ending `_min`/`_sec`/`_minutes`. Allowed:
   `0`, `1`, values in `scheduler/constants.py` (technical timeouts such as undo 15 s, magic link
   15 min, OAuth state 10 min, token refresh 5 min, retry backoff — **not** scheduling rules), and
   lines carrying `# noqa: magic` with a reason. Wire into `make lint`.
8. ruff config: line length 100, rules `E,F,I,UP,B,SIM`; mypy strict for `scheduler.engine`.
**Done when:** `make check` passes on the empty skeleton; the architecture test fails if you add
`import sqlalchemy` to an engine file (try it, then revert).

### F-03 — Web skeleton
**Depends on:** F-01  **Size:** M
**Files:** `web/*` per layout §3
**Steps:**
1. `pnpm create next-app web --ts --app --src-dir --eslint --tailwind --import-alias "@/*" --use-pnpm`
   (Tailwind v4); enable `strict`, `noUncheckedIndexedAccess`; add deps from §2 (drop React Router).
2. `next.config.ts`: `async rewrites() { return [{ source: "/api/:path*", destination:
   `${process.env.API_ORIGIN ?? "http://localhost:8000"}/api/:path*` }] }`; security headers
   (CSP, HSTS, nosniff, frame-ancestors none) via `headers()`; `typedRoutes: true`.
3. Vitest (`vitest.config.ts`, jsdom, `@vitejs/plugin-react` for tests only) + Testing Library + MSW.
4. Prettier; scripts `dev, build, start, test, lint, typecheck, gen:api, e2e`.
5. `src/app/(app)/today/page.tsx` placeholder; `/` redirects to `/today`.
6. Add `vercel.json` only if needed (framework preset Next.js, root directory `web`).
**Done when:** `pnpm build` and `pnpm test` succeed; `make dev-web` serves the page and
`/api/health` reaches the local API through the rewrite.

### F-04 — Local dev stack
**Depends on:** F-02  **Size:** S
**Files:** `deploy/docker-compose.dev.yml`
**Steps:** Postgres 19 (`postgres:19-alpine`, volume mounted at `/var/lib/postgresql` — see DP-02) on `localhost:5433` (avoid clashing with a local PG), volume `pgdev`;
`mailpit` on 1025/8025 for magic-link emails. A second database `tartib_test` created by an init
script for tests.
**Done when:** `make dev-db` then `psql postgresql://tartib:tartib@localhost:5433/tartib -c 'select 1'` works.

### F-05 — CI
**Depends on:** F-02, F-03  **Size:** S
**Files:** `.github/workflows/ci.yml`
**Steps:** jobs `backend` (services: `postgres:19`; `astral-sh/setup-uv` with Python 3.15; `uv sync`, `make lint typecheck`, pytest with
coverage gate: engine ≥ 95 % lines, overall ≥ 80 %), `web` (Node 26, `pnpm i --frozen-lockfile`, lint,
typecheck, vitest, build), `e2e` (on main only; Playwright against `docker compose` stack with
`FAKE_GOOGLE=1`).
**Done when:** a PR shows green checks.
