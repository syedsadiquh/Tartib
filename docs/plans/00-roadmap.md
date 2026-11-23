# 00 — Roadmap & Progress Tracker

**Releases:** each milestone ends with the release shown in its heading (SemVer — see
`12-versioning.md`). Fixes between milestones ship as patch releases.

**How to use:** pick the first unchecked package whose dependencies are all checked, do it
fully (see `README.md` → "How an implementing agent must work"), then tick it here and add a short
note after the `—` if anything was surprising. Sizes: S ≤ 2 h · M ≈ ½ day · L ≈ 1 day.

The plan builds a **walking skeleton with fake Google first** (M0–M4). The app becomes usable
end-to-end in the browser at M7, with real Google from M5 onward. Real Google is deliberately not
on the critical path for the engine or UI.

```
M0 Foundation ─► M1 Data ─► M2 Engine ─────────────┐
                    │                               ▼
                    └──────► M3 Backend core ─► M4 Worker ─► M5 Real Google
                                   │                               │
M6 Web foundation (parallel, MSW mocks) ─► M7 Web core screens ◄───┘
                                   ▼
            M8 Agents & capture · M9 Notifications & PWA · M10 Backup & insights
                                   ▼
                          M11 Deploy & go-live ─► M12 Discord bot (optional)
```

**Parallel tracks** (if several agents work at once — never two on the same package or file):
- Track E (engine): M2 needs M0 + DB-02 (the test builders import `seed/defaults.py`); it touches only `backend/src/scheduler/engine/` and `backend/tests/engine/`.
- Track B (backend): M1 → M3 → M4 → M5.
- Track W (web): M6 can start after F-03 using MSW mocks built from the DTOs in `04-backend-api.md`;
  switch to the generated client as each endpoint lands.

---

## M0 — Foundation  →  release `v0.1.0`
- [x] F-01 Repo hygiene & Makefile — scaffold landed in `46ef9f7`; completed here: `web/.next/` ignored, `API_ORIGIN` documented in `.env.example`, dev section added to README
- [x] F-02 Backend skeleton & architecture guards — src layout on Python 3.15 (uv supplies it; system python is 3.9), console-script stubs and `constants.py` added per D-33, web make targets guarded per D-32; guards proven to fail on a planted `import sqlalchemy` and `datetime.now()`
- [x] F-03 Web skeleton — Next 16.4.6 / React 19.3 / Tailwind 4.3.3 scaffolded; `/api` rewrite + security headers proven against a live uvicorn (`server: uvicorn` on `/api/health`); Vitest+MSW wired (4 tests) and `/` → `/today` verified. `make check` green with no SKIP lines — the D-32 guard retired itself as designed. Dropped `cacheComponents`/`partialPrefetching`/`next/font` from the scaffold (D-36)
- [x] F-04 Local dev stack — compose + `initdb/01-test-db.sql` had already landed in the scaffold and were untested; verified here end-to-end on Docker 29.8: PG 19 healthy on `:5433`, both `tartib` and `tartib_test` accept the app's own psycopg driver, mailpit answers 200 on `:8025`, and `PG_VERSION` sits under `/var/lib/postgresql/19`, proving the 18+ mount path. `psql` is not installed on this host, so the check used psycopg instead of the CLI the plan names. No code changes were needed
- [x] F-05 CI — four jobs in `.github/workflows/ci.yml`; green on PR #16 (`backend` 26 s, `web` 39 s, `openapi drift` 34 s, `e2e` skipped on a branch PR as designed). Dormant gates print `SKIP … (owned by …)` in the real logs, not just in the plan (D-37). First run failed because `uv sync` ran at the repo root instead of `backend/` — fixed in `8bfbced`; the coverage floor is the measured 20.66 % until M3
- [x] F-06 Conventional Commits & release-please — release-please opened its own PR on `main` and cut `v0.1.0` on 2026-11-23 (manifest, `CHANGELOG.md` and both version files bumped by the action, not by hand). `Release-As: 0.1.0` was carried by mini-PR #18 as the runbook prescribes; no commit linting ships (D-38) and scopes are areas (D-39). First tag came out `tartib-v0.1.0` — `include-component-in-tag: false` makes the next one `v0.2.0`

## M1 — Data  →  release `v0.2.0`
- [ ] DB-01 ORM, mixins, migration 0001 —
- [ ] DB-02 Settings models & seeder —

## M2 — Engine (pure)  ← the crown jewel; do not rush  →  release `v0.3.0`
- [ ] EN-01 Types & rule codes —
- [ ] EN-02 Time primitives & builders —
- [ ] EN-03 Frames & office gate —
- [ ] EN-04 Meetings, pinned, frozen —
- [ ] EN-05 Prayers & qada —
- [ ] EN-06 Habits —
- [ ] EN-07 Chunking —
- [ ] EN-08 Ordering & dependencies —
- [ ] EN-09 Task slot search —
- [ ] EN-10 Minimal shrink —
- [ ] EN-11 Planner orchestration & precedence —
- [ ] EN-12 Invariant checker —
- [ ] EN-13 Diff, classification, requires —
- [ ] EN-14 What-if —
- [ ] EN-15 Acceptance & property suite —

## M3 — Backend core (fake Google)  →  release `v0.4.0`
- [ ] WK-01 Job queue (needed early: every mutation enqueues a replan) —
- [ ] BE-01 App factory & errors —
- [ ] BE-02 Actor, activity, audit —
- [ ] BE-05 Settings read service —
- [ ] BE-06 Undo & idempotency —
- [ ] IN-01 Crypto & secrets —
- [ ] IN-13 Email sender —
- [ ] BE-03 Sessions & magic link —
- [ ] BE-04 Passkeys —
- [ ] BE-07 Tasks CRUD —
- [ ] BE-08 Subtasks & dependencies —
- [ ] BE-09 Progress, defer, state —
- [ ] BE-10 Habits CRUD —
- [ ] BE-11 Habit log/skip/streaks/reactivate —
- [ ] IN-07 Prayer times & drift — spec revised: AlAdhan API replaces `adhanpy` (D-35)
- [ ] BE-12 Prayers service —
- [ ] BE-13 Snapshot & plan run —
- [ ] IN-04 Calendar port + fake —
- [ ] IN-06 Outbound writer with rollback —
- [ ] BE-14 Apply plan —
- [ ] BE-15 Placements move/pin/+15m —
- [ ] BE-17 Today & Week read models —
- [ ] BE-18 Log & activity APIs —
- [ ] BE-16 Decisions & day overrides —
- [ ] BE-19 Settings write/export/import/preview —
- [ ] BE-20 Vocabulary API —
- [ ] BE-26 Test-only seed endpoint —
- [ ] BE-27 Instant re-plan & live version (D-29) —

## M4 — Worker  →  release `v0.5.0`
- [ ] WK-02 Scheduled jobs (register only jobs whose handlers exist) —
- [ ] WK-03 Nightly habit rollover —

Note: in M3, `scheduler-cli seed --dev-calendars` creates the fake calendars (02-data-model §4A)
so plans can be applied end-to-end before real Google exists.

## M5 — Real Google (IN-05 also registers its `calendar_sync` job in WK-02's schedule)  →  release `v0.6.0`
- [ ] IN-02 OAuth connect/status/disconnect —
- [ ] IN-03 Calendar discovery & routing —
- [ ] IN-05 Inbound sync —
- [ ] IN-15 Google push notifications (two-way sync) —
- [ ] BE-25 Onboarding support —
- [ ] IN-12 LLM client —
- [ ] BE-21 Agent tokens, scopes, proposals —
- [ ] BE-22 NL capture & bulk import (needed by WEB-14) —

## M6 — Web foundation  →  release `v0.7.0`
- [ ] WEB-01 Tokens, fonts, theme —
- [ ] WEB-02 Component library —
- [ ] WEB-04 API client & hooks —
- [ ] WEB-03 Shells, nav, precedence rail, shortcuts —
- [ ] WEB-05 Auth screens —
- [ ] WEB-06 Command palette —
- [ ] WEB-07 Errors, toasts, offline banner —
- [ ] WEB-28 Live refresh —
- [ ] F-07 Version surfaces (health, footer, mismatch banner) —

## M7 — Web core screens  →  release `v0.8.0`
- [ ] WEB-10 Today —
- [ ] WEB-13 Tasks list —
- [ ] WEB-14 Capture (manual + NL) —
- [ ] WEB-15 Task detail drawer —
- [ ] WEB-17 Habits & editor —
- [ ] WEB-18 Skip / skip-until / delete / reactivate —
- [ ] WEB-19 Prayers —
- [ ] WEB-11 Week grid (desktop, drag = pin) —
- [ ] WEB-12 Week agenda (mobile) —
- [ ] WEB-20 Plan review on the calendar (ghost overlay) —
- [ ] WEB-21 Decisions —
- [ ] WEB-22 Engine log —
- [ ] WEB-24 Settings —
- [ ] WEB-27 Onboarding —

## M8 — Agents & capture (UI)  →  release `v0.9.0`
- [ ] WEB-16 Bulk import & review —
- [ ] WEB-25 Agent access —

## M9 — Notifications & PWA  →  release `v0.10.0`
- [ ] IN-10 Web Push —
- [ ] IN-11 Discord alerts —
- [ ] WK-04 Notifications dispatcher —
- [ ] WK-05 Heartbeat & watchdog —
- [ ] WEB-08 PWA shell —
- [ ] WEB-09 Offline outbox —
- [ ] WEB-26 Push subscription & actions —

## M10 — Backup, insights, recurrence  →  release `v0.11.0`
- [ ] IN-08 Notion mirror —
- [ ] IN-09 Notion restore —
- [ ] BE-23 Insights —
- [ ] WEB-23 Insights screen —
- [ ] BE-24 Recurring tasks —

## M11 — Deploy & go-live  →  release `v1.0.0`
- [ ] DP-01 Dockerfiles —
- [ ] DP-02 Compose with memory caps —
- [ ] DP-03 Caddyfile —
- [ ] DP-04 Secrets & .env —
- [ ] DP-05 VPS bootstrap —
- [ ] DP-06 Deploy script —
- [ ] DP-07 Backups —
- [ ] IN-14 Drive upload for pg_dump (optional) —
- [ ] DP-08 Runbook —
- [ ] DP-09 Vercel deployment of the web app —
- [ ] Manual verification checklist (11-testing.md §4) —

## M12 — Optional  →  release `v1.1.0`
- [ ] BOT-01 Bot skeleton —
- [ ] BOT-02 Commands —
- [ ] BOT-03 Packaging —

---

## Out of scope (do not build — requirements §3)
Meetings/booking links, multi-user, AI prioritisation, native apps, 7-column week on mobile,
importing from Todoist/Linear/Asana.
