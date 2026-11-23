# Tartib

**A prayer-first planner.** Tartib (ترتيب — *order, arrangement*) schedules your tasks and
habits **around the five daily prayers, never over them**, keeps your Google Calendar
truthful as the day changes, and explains every decision it makes.

> **Status:** design complete, build starting. The requirements, engine rules, UI mockups and
> a step-by-step build plan are done; code lands next. Watch the repo to follow along.

---

## Why

Most planners treat prayer as just another event that can be dragged around. Tartib treats it
as the fixed point the rest of the day is arranged around.

The real goal is **trust**: if you can't see why a block moved, you stop using the planner.
So every automatic change records the rule that produced it, and every change you didn't ask
for is either safe and reversible or waits for your approval.

## How it decides

One strict order of precedence. Nothing lower ever displaces something higher:

```
1. Meetings        (read from your work calendar)
2. Prayers         Fajr · Dhuhr / Jummah · Asr · Maghrib · Isha
3. Office hours    (deep, high-effort work stays out)
4. Pinned blocks   (anything you moved by hand)
5. Habits          (shrink under pressure, never displaced)
6. Tasks           (by deadline pressure)
7. Backlog
```

The order itself is editable, and the app warns you if a change would make a prayer yield.

## Features (planned for v1)

**Prayers**
- Fixed preferred times with a computed cross-check (Maghrib from sunset), per-location
  calculation method, and Jummah replacing Dhuhr on Fridays.
- If a meeting overlaps a prayer, the prayer **shifts inside its window**, keeping
  10-minute protected edges.
- If a prayer can't fit at all, it becomes **qada after Isha**. Several stack, and no task may
  ever take a qada slot.
- Marking a prayer prayed early gives the remaining time straight back to your day.
- A drift guard flags it when the computed time disagrees with the library, so the evening
  never moves silently.

**Habits**
- Ideal and minimum duration, a time window, and the days of the week it runs.
- Under pressure a habit **shrinks by exactly what's needed**, never below its minimum, and
  only after every other option is tried.
- Streaks count per occurrence. Three skips in a row end the streak, and "skip until" pays
  that cost too, with a warning before you confirm.
- Skipping a habit hands its time to whatever was waiting for it, and shows you what that is.

**Tasks**
- Estimates, deadlines, priority, effort, subtasks with weighted minutes, and dependencies.
- **Partial scheduling:** whatever fits is placed and the remainder is flagged. The engine
  never overbooks you and never drops a task silently.
- When the day is overloaded it **stops and reports the exact shortfall**, then offers levers
  (push the deadline, skip a habit, extend the day, trim the task) and never chooses for you.
- Quick capture: `2h DBMS revision before fri, high` becomes chips you can edit. This works
  without AI, and an optional model helps with messy input.
- Bulk import from a syllabus or list, with a review table before anything is created.

**Calendar & review**
- **Google Calendar** is where the plan appears, in your own calendars (Prayers, Learnings,
  Family, …). It syncs both ways within seconds.
- Proposed changes show **on the calendar** as dashed "ghost" blocks: accept, postpone,
  choose a later date, or drag them somewhere else.
- Safe changes apply automatically; anything that moves your day around asks first.
- An **engine log** records every decision with the rule that made it.

**Everywhere**
- Installable **PWA** for phone and desktop, works offline (read view plus queued writes),
  with push notifications for block start, prayer time, plan approval and overload.
- Scoped API tokens for agents and bots. Every change an agent makes is marked **AI**, and
  **AUTO** if it applied without asking.
- Notion mirror for backup, with a dry-run restore.
- Single user and self-hosted. Every rule lives in Settings, not in code.

## Architecture

```
Phone / Browser ──► Next.js PWA (Vercel) ──/api rewrite──► FastAPI ──► Postgres
                                                               │
                                            worker (re-plans, sync, notifications)
                                                               │
                                     Google Calendar · Notion · Web Push
```

- **Engine:** a pure, deterministic Python module. Same inputs, same plan. Every acceptance
  scenario is an automated test.
- **Backend:** Python 3.15, FastAPI, SQLAlchemy 2.1, PostgreSQL 19, a Postgres-backed job queue and
  APScheduler.
- **Web:** Next.js 16, React 19, TypeScript, Tailwind, TanStack Query, PWA with Serwist.
- **Hosting:** one small VPS (Docker Compose, ~1 GB memory cap, Caddy TLS) for the API,
  worker and database; the web app on Vercel.

## What's coming to this repo

```
docs/        requirements, engine spec, decision log, build plans (work packages + roadmap)
mockups/     desktop and mobile screen designs
backend/     API, scheduling engine, worker
web/         Next.js PWA
deploy/      Docker Compose, Caddy, server scripts
bot/         optional Discord shim
```

## Local development

Prerequisites: `uv` (Python 3.15), `pnpm`, Docker (for Postgres + mailpit).

```bash
cp .env.example .env        # fill APP_ENCRYPTION_KEY, APP_SESSION_SECRET, OWNER_EMAIL
make dev-db                 # Postgres on :5433, mailpit UI on :8025
make migrate seed           # schema + default settings
make dev-api                # FastAPI on :8000 (FAKE_GOOGLE=1 needs no Google account)
make dev-worker             # job queue + scheduled jobs
make dev-web                # Next.js on :3000, rewrites /api → :8000
make check                  # lint + typecheck + all unit/service/API tests
```

`make help` lists every target. Real Google Calendar is off the critical path: with
`FAKE_GOOGLE=1` (the dev default) the API talks to an in-memory calendar.

## Non-goals

Tartib is not a meeting or booking tool, not multi-user, and won't let an AI decide your
priorities. It is a PWA rather than a native app.

## License

[MIT](LICENSE) © 2026 Syed Sadiqu Hussain
