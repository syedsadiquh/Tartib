# Tartib — Build & Running-Cost Analysis

Scope: what it takes to build and run Tartib as a 24×7 hosted service for a single user.

---

## 1. Why a custom engine

General-purpose scheduling tools offer tasks, habits and auto-scheduling, but none of them
combine the rules Tartib is built around:

- prayers as fixed anchors, with window shifting and qada after Isha;
- strict, user-editable precedence, where nothing lower ever displaces something higher;
- minimal, floored habit shrinking ("give exactly what's needed, never below the minimum");
- effort-gated office hours, weighted subtasks, dependency chains;
- per-occurrence streaks with a deliberate cost for skipping;
- an explanation and a review step for every automatic change.

The engine is the product; the UI and storage around it are conventional. The build plans
therefore treat the engine as a pure, fully tested module (`docs/plans/03-engine.md`).

## 2. Architecture

```
Phone / Browser ──► Next.js PWA (Vercel) ──/api rewrite──► FastAPI ──► Postgres
                                                               │
                                            worker (re-plans, sync, notifications)
                                                               │
                                     Google Calendar · Notion · Web Push
```

- **Backend:** Python 3.15, FastAPI, SQLAlchemy 2.1, PostgreSQL 19, a Postgres-backed job queue plus
  APScheduler in a separate worker process.
- **Web:** Next.js 16 PWA on Vercel (free tier), same-origin to the API through a rewrite.
- **Calendar:** Google Calendar is the display layer, synced both ways within seconds.
- **Auth:** single user, passkey or magic link. No RBAC, no billing, no multi-tenancy: this
  removes the largest parts of a typical SaaS build.
- **PWA only:** installable, offline read view, Web Push. No app-store fees or review cycles.

Details: `docs/plans/01-architecture.md`.

## 3. Server sizing

Single user, a few dozen calendar writes per hour, occasional UI sessions. The binding
constraint is **reliability**, not compute.

| Component | Memory | Notes |
|---|---|---|
| Caddy (TLS, reverse proxy) | ~30–50 MB | API host only |
| FastAPI API | ~150–250 MB | one uvicorn worker |
| Worker (APScheduler + queue) | ~120–200 MB | plans, sync, notifications |
| Postgres 19 | ~150–300 MB | < 1 GB of data for years of use |
| **Total** | **≈ 0.5–1 GB** | hard-capped at ~1 GB (NFR-10) |

A 2 vCPU / 4 GB VPS is more than enough. The web app runs on Vercel and uses no VPS memory.

## 4. Running cost (monthly)

| Line | Cost |
|---|---|
| Small VPS (2 vCPU / 4 GB, daily snapshot included where available) | ≈ $4–6 |
| Web hosting (Vercel Hobby) | $0 |
| Hostname (DuckDNS) + TLS (Let's Encrypt via Caddy) | $0 |
| Backups (provider snapshot + Notion mirror) | $0 |
| Monitoring (Healthchecks.io free tier) | $0 |
| AI for natural-language capture (optional) | a few cents |
| **Total** | **≈ $5** |

The scheduling engine is deterministic and uses no AI, so there is no per-plan token cost.

## 5. Build effort

Estimates per milestone in `docs/plans/00-roadmap.md`, for one developer working with a
coding model:

| Milestone | Scope | Days |
|---|---|---|
| M0–M1 | Repo, tooling, CI, schema, settings seed | 2–3 |
| M2 | Pure engine with acceptance and property tests | 4–6 |
| M3–M4 | Backend core (fake Google), worker | 5–7 |
| M5 | Real Google: OAuth, discovery, two-way sync | 2–3 |
| M6–M7 | Web foundation and core screens | 7–10 |
| M8–M10 | Agents and capture, notifications and PWA, backup and insights | 5–7 |
| M11 | Deploy and go-live | 1–2 |
| **Total** | | **≈ 26–38 dev-days** |

Add 20–30% for verification against the real calendar. The engine invariants make mistakes
visible early, but they also mean more tests to get green.

## 6. Risks

- **Engine correctness.** The scheduling rules are the crown jewel and the most likely thing
  to break. They are mitigated by a pure engine, the acceptance scenarios A1–A10 as tests,
  property tests for every invariant, and review-before-write.
- **Silent downtime.** A dead server must alert, not fail quietly: a heartbeat, an external
  dead-man check and a watchdog for missed runs (NFR-3/4).
- **Google OAuth.** The consent screen must be published to *Production*; tokens issued in
  *Testing* mode expire after 7 days. The redirect URI needs a real HTTPS hostname.
- **Push notifications from Google** require a public HTTPS endpoint. If they are refused,
  polling every minute is the fallback.
- **Vercel rewrite limits** (timeouts, body size) must comfortably exceed the slowest API
  call (plan apply, normally a few seconds).
