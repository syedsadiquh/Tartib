# Decision Log

Every place where the plans resolve an ambiguity, a contradiction, or a gap in
`01-requirements.md` / `02-engine-spec.md` is recorded here. **The requirements docs stay the
source of truth for product rules; this file records how the build interprets them.**

Implementing agents: if you hit a new ambiguity, **stop, add an entry here with status
`PROPOSED`, and choose the most conservative option** (the one that writes less, moves less, and
flags more). Never silently invent a rule.

Status values: `ACCEPTED` (owner agreed or it is a direct consequence of the spec) ·
`PROPOSED` (planner's call — owner should confirm; build may proceed with it).

---

## D-01 — Engine is built from the spec as a pure module · ACCEPTED (owner, 2026-11-22)

**Decision.** Build a **pure, deterministic engine package** (`backend/src/scheduler/engine/`)
from `02-engine-spec.md`, with every acceptance scenario (A1–A10) and every invariant as an
automated test. No earlier scripts are reused: every rule must be data-driven from Postgres
(**SET-0**), and the core rules (qada stacking, minimal shrink, per-occurrence streaks,
editable precedence) are specified here for the first time.

## D-02 — Frontend is Next.js on Vercel (free); API stays on the VPS · ACCEPTED (owner, 2026-11-22)

**Superseded proposal:** Vite SPA served by Caddy. **Owner's decision:** Next.js deployed on
**Vercel (Hobby, free)**. This also takes the web build and static hosting off the 1 GB VPS.

How it fits together:
- Next.js **App Router**; every screen is a client component (`"use client"`) using TanStack
  Query against the API, so no server component ever needs the user's cookie. Server
  components are used only for layouts and static shells.
- **Same-origin API through Vercel rewrites:** `next.config.ts` rewrites `/api/:path*` →
  `${API_ORIGIN}/api/:path*` (the VPS, e.g. `https://tartib-api.duckdns.org`). The browser only
  ever talks to `https://tartib.vercel.app`, so the session cookie, CSRF header, passkeys (RP id =
  Vercel host) and the Google OAuth callback (`https://tartib.vercel.app/api/google/callback`) all
  work without CORS.
- The API host is still public (Caddy + Let's Encrypt on DuckDNS) because Vercel and Google's
  push webhooks (D-29) must reach it. Every route still requires a session or an agent token.
- PWA via **Serwist** (`@serwist/next`); manifest via `app/manifest.ts`; fonts via `next/font`.
- Verify at build time: Vercel's limits for external rewrites (timeout, body size). Plan apply
  normally finishes in a few seconds, well inside them.

> **SUPERSEDED — do not implement.** Earlier proposal, kept for history:
> The docs mention Next.js. The app is single-user, behind auth, with no SEO and no SSR value,
> and NFR-10 caps the whole stack at ~1 GB. A Next.js server costs 150–250 MB RAM for nothing.
> **Decision:** Vite + React + TypeScript, built to static files and served by Caddy. Zero
> runtime memory. Same component ecosystem.

## D-03 — "App" means the installable PWA · ACCEPTED

Requirements §3 makes native apps a non-goal. The "mobile app" is the same web codebase with
a mobile layout (< 768 px), installable to the home screen, with Web Push. The typed API client
lives in `web/src/api/` and is generated from OpenAPI, so a future native client could reuse
the contract.

## D-04 — Process split: `api`, `worker`, `db`, `caddy` (+ optional `bot`) · ACCEPTED

NFR-1 lists API, worker, Postgres, Caddy. APScheduler runs in the **worker** process only (never
inside uvicorn workers, which would double-fire jobs). The API enqueues work in a Postgres
`job` table; the worker polls it. No Redis.

## D-05 — Minimum chunk applies to task chunks only · ACCEPTED (owner, 2026-11-22)

FR-3 says "no block shorter than 30 minutes", yet the defaults include Qur'an 15m, Skincare PM
10m, and prayers of 20–25m. **Decision:** `min_chunk_min` governs **task chunks** (and the
remainder rule of TSK-4). Habits use their own `min_min`/`ideal_min`; prayers use their own
duration.

## D-06 — Prayer preferred time is always valid; edge protection governs shifts · ACCEPTED (owner, 2026-11-22)

PRY-2 says a prayer must fit in `[window_start+10, window_end−10]`, but A1 uses Dhuhr at 13:00
with window 13:00–14:00, so the preferred time itself would be illegal. **Decision:** if the
preferred slot `[anchor, anchor+duration]` is free, the prayer is placed there. When it must
**shift**, every candidate must lie fully inside the protected core.

## D-07 — Prayer-after-meeting transition gap (default 5m) · ACCEPTED (owner, 2026-11-22)

A1 expects Dhuhr to move to **13:20**, not 13:15, after a meeting ending at 13:15, and it fits
inside the core (13:10–13:50). The only consistent reading is a short transition gap.
**Decision:** setting `prayers.meeting_gap_min` (default **5**). When a prayer shifts to avoid
a meeting, it must start ≥ `meeting.end + gap` (or end ≤ `meeting.start − gap`). A1 then yields
13:20 exactly.

## D-08 — "Flagged" is a flag on the task, not a lifecycle state · ACCEPTED (owner, 2026-11-22)

§19 lists `flagged` as a task state; TSK-3 does not. A task can be `scheduled` (3h placed) **and**
flagged (30m short) at the same time (TSK-5), so the flag is orthogonal. **Decision:**
`task.state` ∈ {inbox, scheduled, in_progress, partial, done, skipped, backlog}; the flag is
`task.flag_code` + `task.flag_reason` + `task.flag_short_min` (null when not flagged). The UI
filter "Flagged" queries `flag_code IS NOT NULL`.

## D-09 — Task slot order: earliest-first by default, configurable · ACCEPTED (owner, 2026-11-22)

Engine spec §7 reads as "deadline day first, then earlier days", ENG-1 reads as "any free slot,
then earlier days". The mockups show tasks placed early. **Decision:** setting
`block_rules.placement_order` ∈ {`earliest_first` (default), `deadline_first`}. Earliest-first
keeps slack for later re-plans. The owner can flip it.

## D-10 — Stickiness: a block keeps its previous slot when still valid · ACCEPTED (owner, 2026-11-22)

ENG-5 (pre-clean) plus a from-scratch planner causes churn: one new task can move ten blocks.
**Decision:** previous engine placements are passed to the engine as **hints only** (not as
occupied time). When a **task** is processed, its previous slots are tried first if they are
still entirely valid. Then the normal search runs. Habits do **not** use hints: they always aim
for their ideal time, so a habit pushed aside by a meeting returns to its ideal slot once the
meeting is gone. This keeps ENG-4 idempotence and cuts noise
in the review sheet.

## D-11 — Shrinking frees time from the habit's tail or head, never the middle · ACCEPTED (owner, 2026-11-22)

HAB-3 defines *how much* to shrink, not *where*. **Decision:** the engine evaluates shrinking from
the end (habit keeps its start) and from the start (habit keeps its end), and picks the option
that needs the smaller shrink (ties → tail). The freed span is merged with adjacent free time.
The shortfall includes the buffer the task chunk needs after it.

## D-12 — Atomic tasks are all-or-nothing · ACCEPTED (owner, 2026-11-22)

TSK-5 ("schedule what fits") conflicts with split = Atomic. **Decision:** atomic tasks are
placed whole or not at all. If not, they are flagged with the full shortfall. Shrink may still
be used to make room.

## D-13 — Dependencies: a dependent may be scheduled after a *fully placed* dependency · ACCEPTED (owner, 2026-11-22)

TSK-7 says "never schedules before its dependencies complete", but the review mockup schedules
W2D2 (depends on W2D1) in the same import. **Decision:** a dependent task may be placed only
**after the end (+ buffer) of its dependency's last placed chunk**, and only if the dependency is
`done` or **fully placed** in this run. If the dependency is flagged, blocked or unplaced, the
dependent is blocked with `TASK_BLOCKED_DEPENDENCY` and the chain is shown.

## D-14 — Diff classification: smart auto-apply of new blocks · ACCEPTED (owner, 2026-11-22)

RPL-3 lists only same-day moves and habit shrinks as Safe. The owner chose: **new blocks are
added automatically when it is clearly safe; anything that isn't clearly safe waits for review**,
and review happens **on the calendar** (D-28). The owner explicitly enabled auto-apply, so
`block_rules.auto_apply_safe` defaults to **true** (RPL-4 satisfied: it is the user's choice,
switchable off in the review header and in Settings).

**Decision:**
- `create` → **safe** only when *all* of these hold (setting `block_rules.auto_apply_creates`
  = `when_safe`, the default; `never` makes every create ask):
  1. it displaces nothing — its `requires` list is empty (it only uses free time);
  2. no habit was shrunk to make room for it in this run (block meta `shrunk_for_task_id`);
  3. its task is not flagged in this run and the chunk is not overflow (`meta.overflow`);
  4. it starts at least `block_rules.safe_create_lead_min` (default **60**) after now — a
     block that is about to start always gets a look;
  5. it is a task chunk, habit or prayer of a source that already had placements before, **or**
     a task created by the user (tasks created by an agent without auto-approve never reach
     here; agent-created tasks with auto-approve are still marked AI/AUTO).
  6. **Exception: time the user just released.** If the re-plan was triggered by the user freeing
     time (habit skip, qada/prayer marked prayed early, task done/skipped/deferred, block removed),
     the job carries the released intervals. A create that lies **entirely inside** a released
     interval is **safe even when its task is flagged and even if it starts within the lead time**,
     as long as rules 1–2 hold. The skip toast already told the user what the freed time enables
     (HAB-12), so the flagged task schedules itself at once (D-17).
  Otherwise → **ask**.
- `move` same day → safe · `move` across days → ask
- `resize` of a habit (shrink **or** restore) → safe · `resize` of a task chunk → ask
- `delete` because the source was completed / skipped / deleted / deferred **by the user** → safe (cleanup)
- `delete` for any other reason → ask
- prayer shift/qada within the same day → safe, **unless** the prayer has a drift flag → ask
- anything touching a pinned block → never emitted

## D-15 — Pinned blocks vs higher ranks · ACCEPTED (owner, 2026-11-22, amended)

**Owner's amendment:** placing a block over a **meeting** is legitimate. The owner may skip a
meeting, or attend passively while doing other work, and wants to put the block they actually
worked on there, including **after the fact**. So:
- A pinned block overlapping a **meeting** raises **no flag**. It is shown with an
  "over meeting" marker, and both stay on the calendar.
- A pinned block overlapping a **prayer or qada** still raises `PINNED_CONFLICT`, because prayers
  never yield (PRY-7).
- The user can create or move a task or habit block into the **past** (e.g. over the meeting they
  sat through). That counts as **logged work**: task `logged_min` or habit `actual_min`
  increases (BE-15).

Original text (still applies except where amended above):



The engine never moves a pinned block (ENG-3). If a pinned block overlaps a higher-ranked item
(meeting, prayer), the higher item is still placed as if the pinned block weren't there. The
pinned block gets a `PINNED_CONFLICT` flag for the user to resolve. The DB no-overlap
constraint excludes pinned rows. FR-7's "no double-booking" therefore covers every block the
**engine** creates.

## D-16 — Precedence is data: the generic rule · ACCEPTED (owner, 2026-11-22)

SET-5 makes the order editable. **Decision:** the engine places categories **in precedence
order**. When placing rank *R*, everything already placed (ranks above *R*) is an obstacle.
Fixed categories (meetings, pinned) are "placed" at their own rank. A higher-ranked placement
may overlap a lower-ranked fixed block, which is then flagged. `office_hours` is a constraint,
not a block: it applies its High-effort exclusion to every category ranked below it.

## D-17 — Missed occurrence resets streak but does not end the habit · ACCEPTED (owner, 2026-11-22, clarified)

**Owner's clarification of intent:** skipping exists so that when a habit was shrunk to its floor
and a task is **still short and flagged**, the owner can skip the habit and the task
**immediately and automatically** takes the freed time. That is D-14 rule 6: creates inside
time the user just released are auto-applied. Skipping still costs the streak: **3 consecutive
skipped occurrences reset it**, including the occurrences covered by a "skip until" span longer
than 3 days, and the picker warns before confirming (HAB-7, HAB-8, HAB-8a, unchanged). As in the
requirements, the third skip also marks the habit ended, with a one-tap Reactivate.

Original text (still applies except where amended above):



HAB-9: a miss "breaks the streak immediately". HAB-7: three consecutive skips "end" the habit.
**Decision:** a miss sets `streak_current = 0` and leaves the habit `active`. Only the skip
threshold sets `state = ended`. The skip counter is reset by a *done* log only. A miss does not
reset it.

## D-18 — Google OAuth client credentials: UI-editable, encrypted at rest · ACCEPTED (owner, 2026-11-22)

SET-0/SET-1 want Google credentials editable in the UI; NFR-6 wants secrets in env.
**Decision:** only the **master key** `APP_ENCRYPTION_KEY` lives in env (plus DB password).
The OAuth client id/secret, tokens, Notion token and LLM key may be entered in Settings and are
stored encrypted with that key. Env vars, if present, act as defaults.

## D-19 — Natural-language capture: deterministic parser first, LLM optional · ACCEPTED (owner, 2026-11-22, extended)

**Owner's extension:** the deterministic (no-AI) parsing also helps the **manual form**:
- The Estimate field accepts `1h30`, `1h 30m`, `90m`, `1.5h`.
- The Deadline field accepts `fri`, `tomorrow`, `tomorrow 5pm`, `next week`, `25 nov`.
- Typing a title like "DBMS revision before fri, high" fills **only empty** fields, each marked
  *inferred* with × to clear.

No network call and no model are involved (CAP-5 holds). The parser is one shared TS module
(`web/src/features/capture/parse.ts`), and its cases are mirrored by the backend parser tests.

Original text (still applies except where amended above):



CAP-7 confines AI to NL capture. **Decision:** a local rule-based parser (durations, "before
Fri", priority words, subject keywords) always runs first. The LLM is called only when NL
capture is enabled in Settings **and** the user submits a free-text line. The LLM output goes
through the same draft form (CAP-8). With no key configured, NL capture still works at reduced
accuracy.

## D-20 — Recurring tasks are materialised instances · ACCEPTED (owner, 2026-11-22)

TSK-9 gives no model. **Decision:** a task may carry `recurrence` (`{freq: daily|weekly,
interval, weekdays?, count?, until?}`). The worker materialises plain task instances into the
planning window (each with its own deadline = end of its occurrence day unless configured).
Instances are normal tasks, so they never compress anything special.

## D-21 — Day-edge overrides implement "Make time" · ACCEPTED

OVL-2 "make time (extend the day's edge)" is stored as a `day_override` row (`date`,
`earliest_block`, `latest_block_end`). Office hours are never edited (OFF-3).

## D-22 — Undo is server-side · ACCEPTED (owner, 2026-11-22)

UX-2 needs a 10-second undo. Every reversible mutation returns an `undo_token`. The server stores
the inverse operation for 15 s (5 s grace beyond the toast). `POST /api/undo/{token}` applies it.

## D-23 — Login: passkey primary, magic link fallback, CLI recovery link · ACCEPTED (owner, 2026-11-22)

SET-13 asks for passkey or magic link. Magic link needs an email sender (SMTP settings). For a
first boot with nothing configured, `scheduler-cli login-link` prints a one-time link to the
server console. This is the only CLI step, and it is about auth, not Google (SET-1 is
unaffected).

## D-24 — Overflow after the deadline (TSK-5 step 4) · ACCEPTED (owner, 2026-11-22)

TSK-5 says that if time never opens, the remainder "splits to later free time, keeping its flag".
**Decision:** after normal search and shrinking, any remaining minutes are placed in free time
**after the deadline** (still inside the planning window), as chunks with `meta.overflow=true`
and rule `TASK_OVERFLOW`. The task keeps its `TASK_PARTIAL_FLAGGED` flag and its before-deadline
shortfall. When time opens before the deadline, the next plan moves the work there and deletes
the overflow chunk (A5 still holds). Engine invariant 4 exempts overflow chunks.

## D-25 — Tasks shorter than the minimum chunk · ACCEPTED (owner, 2026-11-22)

FR-3 says no block under 30m, yet the mockups show 20m tasks ("Inbox triage 20m").
**Decision:** (a) a task whose **whole estimate** is below `min_chunk_min` is placed whole at its
own length, because it cannot be split smaller than itself; (b) a **remainder** left by partial
progress (TSK-4) is rounded **up** to `min_chunk_min` ("re-chunked to ≥ 30m"). No split ever
creates a piece smaller than the minimum.

## D-26 — Everything the engine places sits on the slot grid · ACCEPTED (owner, 2026-11-22)

Owner: the grid is **5 minutes**; any multiple of 5 within the hour is valid (e.g. 18:35–19:20).
`slot_granularity_min` defaults to 5 and cannot be set below 5.


Durations that are not multiples of `slot_granularity_min` would produce off-grid blocks. **Decision:**
the API rejects estimates, weights, habit durations and progress minutes that are not multiples
of the grid (422 `NOT_ON_GRID`). The engine also rounds task needs and habit lengths **up** to
the grid, defensively. Prayers keep their configured anchors (e.g. 15:35) and are exempt from the
grid invariant.

## D-27 — Prayed-early release is a user action, not an engine change · ACCEPTED (owner, 2026-11-22)

PRY-6 frees time when a qada or prayer is marked prayed early. **Decision:** the API truncates
(or removes) the prayer's block and writes that to Google at once (BE-12), then triggers a
re-plan. The engine never emits blocks for prayed prayers. Any leftover engine block for one is a
safe `PRECLEAN_SOURCE_CLOSED` delete.

## D-28 — Plan review happens on the calendar · ACCEPTED (owner, 2026-11-22)

The owner found the list-only review sheet hard to read: a list of times doesn't show the whole
picture. **Decision:** proposed changes are drawn **on Today and Week** as hollow, dashed "ghost"
blocks at their new position. A moved block keeps a faded copy at its old position with a
connector, and a removed block is shown struck through. The list stays as a compact side panel
(desktop) or bottom bar (mobile) for keyboard use and for flags. On every ghost the owner can:
**Accept**, **Not now** (suppress that change for 24 h), **Later date** (defer the task —
Tomorrow / Next week / pick a date — which re-plans at once), or **drag** it to another slot
(accept there, pinned). Blocks that were auto-applied carry the AUTO marker, and their drawer
offers *Later date* and *Move*, so reversing an automatic decision is one tap. Applying still
asks for the single hard confirm (UX-3).

## D-29 — Near-instant re-planning and two-way sync · ACCEPTED (owner, 2026-11-22)

The owner wants an updated plan within seconds of any change, not at the next hourly run.
Changes must appear in Google Calendar directly, and Google-side changes must flow back.
**Decision:**
1. **Every change triggers a re-plan** (tasks, habits, prayers, settings, vocab, drag/pin,
   agent writes, calendar sync). `block_rules.replan_debounce_sec` defaults to **2** s, enough
   to coalesce a burst of edits. The worker polls the queue every **1 s**. The hourly run stays
   as a safety net only.
2. **Safe changes go to Google immediately.** Auto-apply is on (D-14), so typical latency from
   edit to Google Calendar is about 3–6 s. Ask-level changes appear instantly in the app as ghost
   blocks (D-28) and reach Google after one tap.
3. **Google → app via push notifications.** The app registers `events.watch` channels for
   every enabled calendar that feeds meetings or is writable. Google calls
   `POST /api/google/webhook` on the API host. The handler verifies the channel token and
   enqueues an incremental sync of that calendar (run within ~1 s), which triggers a re-plan if
   anything relevant changed. Channels are renewed before expiry. Polling every
   `google.sync_interval_min` (default **5**) remains as a fallback if webhooks fail. If Google
   refuses the webhook host, polling drops to every 1 minute automatically.
4. **The open app refreshes itself.** A Postgres trigger bumps a single `data_version` counter on
   every schedule-relevant write. The web client polls `GET /api/version` every 5 s while
   visible (every 1 s for 20 s after the user's own mutation) and refetches when the version
   changes. This works through Vercel rewrites, unlike long-lived streams.

## D-30 — Latest stable versions everywhere · ACCEPTED (owner, 2026-11-22)

The owner wants the stack current going into v1 and kept current afterwards. **Decision:**
- Baseline: Python 3.15, PostgreSQL 19, Node 26 LTS, Next.js 16, React 19, Tailwind 4.3,
  SQLAlchemy 2.1, psycopg 3.3, FastAPI, Pydantic 2, TanStack Query 5.
- Exception: APScheduler stays on 3.x, because 4.0 is still a pre-release with a different
  API. Revisit when 4.0 is stable.
- Postgres 18+ features used: built-in `uuidv7()` for all primary keys (no `pgcrypto`).
- Policy (01-architecture "Version policy"): latest stable at implementation time, exact pins in
  lockfiles, weekly Renovate PRs gated by CI, and no pre-releases.
- Checked: all compiled Python dependencies (psycopg-binary, pydantic-core, cryptography, uvloop,
  httptools) resolve as binary wheels for Python 3.15 on linux/x86_64.

## D-31 — Semantic Versioning for the whole repo · ACCEPTED (owner, 2026-11-22)

The owner chose `vMAJOR.MINOR.PATCH` with the standard rules. **Decision:**
- One version for backend, web and bot.
- Before 1.0: each completed roadmap milestone is a MINOR release (`v0.1.0` … `v0.11.0`); fixes
  are PATCH; breaking changes bump MINOR and are flagged.
- `v1.0.0` ships when the go-live checklist is green, after `-rc` soak builds.
- From 1.0: MAJOR = incompatible public API change (HTTP API, rule codes, settings export,
  Notion layout, manual migrations), MINOR = compatible feature, PATCH = fix.
- Conventional Commits (scope = work-package ID) plus release-please produce tags, GitHub
  Releases and `CHANGELOG.md`. Details: `docs/plans/12-versioning.md`.

## D-32 — Web make targets no-op until F-03 exists · PROPOSED (F-02)

F-02's *Done when* is "`make check` passes on the empty skeleton", but `make check`
(`lint` → `typecheck` → `test`) invokes `pnpm` inside `web/`, which has no `package.json`
until F-03. Without a guard the gate is unachievable, and F-03 is not F-02's dependency.

**Decision:** the four web-facing targets (`lint`, `typecheck`, `test-web`, `test-e2e`)
guard on `web/package.json` and print `SKIP … (F-03)` when it is absent. The guard is
keyed to that file, so it disappears by itself the moment F-03 lands — nothing to remove
later, and CI (F-05) still runs the real command once the app exists.

Trade-off accepted: a green `make check` during M0 says nothing about the web app. The
skip line is printed on every run so it can never be mistaken for a pass.

## D-33 — F-02 creates three files its Files list omits · PROPOSED (F-02)

F-02 lists `config.py`, `clock.py`, `db.py`, `api/app.py`, `tests/test_architecture.py`
and `scripts/check_no_magic_numbers.py`, but its own steps require three more modules:

- `constants.py` — `check_no_magic_numbers.py` must read the allow-list of technical
  timeouts from somewhere, and ARCH §3 already places this file in the layout. Populated
  with only the transport timeouts named in F-02 step 7 (undo, magic link, OAuth state,
  token refresh, retry backoff), plus the queue poll interval and calendar write attempts
  from D-29/IN-06. No scheduling value lives here (SET-0).
- `cli.py` — `pyproject.toml` declares `scheduler-cli = "scheduler.cli:main"`; the entry
  point must resolve. Ships as a parser that errors on unknown commands; each package adds
  its own subcommand when it owns one.
- `engine/__init__.py` — `mypy src/scheduler/engine` and the architecture test both walk
  that path, and EN-01 fills the package.

**Decision:** ship all three as the minimum that makes F-02's stated gate pass, with no
behaviour beyond that. Conservative: no command is implemented, no scheduling constant is
introduced, no engine symbol is defined.

## D-34 — Branch names describe the change; the package ID stays in the commit scope · PROPOSED (F-02)

`AGENTS.md` and `12-versioning.md` require the work-package ID as the Conventional Commit
scope. Neither prescribes branch naming, and branches like `feat/F-02-…` read as code
rather than as a change.

**Decision:** branches are `type/kebab-description` cut from `develop`
(`feat/backend-skeleton`), and the package ID appears only in the commit scope
(`feat(F-02): …`) and the PR title. The roadmap line remains the authoritative
package → change mapping, so nothing depends on the branch name.

## D-35 — Prayer times come from the AlAdhan API, not a local library · PROPOSED (owner request, 2026-11-23)

The owner asked to replace `adhanpy` with the **AlAdhan prayer-times API**
(`https://api.aladhan.com/v1`, contract: their OpenAPI v1 document). PRY-1/PRY-8 do not
name an implementation, so the product rules are unchanged; IN-07's implementation and one
settings field change.

**Decision.**
- `integrations/prayer_times.py` becomes a port (`PrayerTimes.times(days, cfg)`) with an
  `AlAdhanTimes` httpx client and a `FrozenTimes` fake; the API is the **reference** value.
- `PrayerSettings.method` (an `adhanpy` enum name string) becomes **`method_id: int = 1`**
  — the AlAdhan `method` id (1 = University of Islamic Sciences, Karachi, which preserves
  the old `KARACHI` default and the 18°/18° angles the plan's cross-check assumes).
  `madhab` is unchanged in the settings and is sent as AlAdhan `school` (0 shafi, 1 hanafi).
  Nothing has shipped, so no data migration is needed; DB-02 seeds `method_id`.
- **Dates go in the path as `DD-MM-YYYY`.** Verified against the live API on 2026-11-23:
  `timings/2026-11-23` returns **2023** timings for that day/month, and
  `calendar/from/2026-11-20/to/2026-12-04` returns `500 SERVER_ERROR`, while the same
  requests with `23-11-2026` / `20-11-2026` are correct. The client therefore formats the
  path dates itself and **rejects any response whose date is not the one requested**.
- One range request per calendar month (`/calendar/from/{start}/to/{end}`) with
  `iso8601=true` and `timezonestring={settings tz}`, so times arrive tz-aware; the API's
  11-month range cap never applies to our 14-day planning window.
- The API's per-prayer `tune` string is **not** used: `PrayerConfig.computed_offset_min`
  already tunes the anchor, and two tuning knobs would silently double-apply.
- **No Postgres cache table.** The in-process cache plus the in-house NOAA computation as
  fallback keeps IN-07 self-contained (DB-01 has no schema for it) and keeps PRY-8's
  disagreement visible instead of burying it in stale rows.
- Failure path is the conservative one: cache → NOAA cross-check with
  `PRAYER_TIMES_UNAVAILABLE` (never a silently shifted prayer, never a missing one).
  Unknown `method_id` → no cross-check, flag `PRAYER_DRIFT_UNVERIFIED`.
- `adhanpy` is removed from `backend/pyproject.toml` and `uv.lock`; `solar.py` stays.

**Trade-off accepted:** an external service is now on the rendering path for computed
prayers. It is unauthenticated, cheap (one call per month per config), and the fallback
path means an outage degrades to in-house timings plus a visible flag rather than a gap.

**Deferred — calculation options the owner will need (owner note, 2026-11-23).** The owner
wants the app to expose the rest of AlAdhan's calculation surface, not just method and
madhab: `latitudeAdjustmentMethod` (1–3), `tune` (nine per-prayer minute offsets),
`shafaq` (method 3 only) and `midnightMode` (0/1). IN-07 ships defaults only; the settings
model and the settings screen grow the optional fields in a later package (see the table in
`05-integrations.md` § IN-07). They are optional with the API's own defaults so saved
settings stay valid, and `solar.py`'s per-method angle table must gain an entry for every
`method_id` offered in the UI — otherwise the drift guard reports
`PRAYER_DRIFT_UNVERIFIED`. Recorded now so the backend settings skeleton is shaped for it;
nothing is implemented in this change.

## D-36 — F-03 pins Node 26 / pnpm 12 and drops two scaffold defaults · PROPOSED (F-03)

Three choices F-03 had to make that the plans either contradict or leave open.

**Decision.**
- **pnpm 12, not 10.** `01-architecture.md` §2 still says "pnpm 10 (via corepack)", but
  accepted decision D-30 says *latest stable, pinned in the lockfile*. The registry's current
  stable is 12.14.0 and `web/package.json` pins it via `packageManager`. §2's table row is
  stale — it should be read as "pnpm 12" and corrected when that table is next edited.
- **Node 26 via `.nvmrc`, enforced only where it matters.** This machine's default `node` is
  22.14; Node 26 LTS is what the plan pins. `web/.nvmrc` = `26`, `engines.node` = `>=26.0.0`.
  `engines` alone is advisory (pnpm does not enforce it for scripts, and `engine-strict` only
  guards installs), so the **test** scripts run `scripts/check-node.mjs` first: a wrong
  interpreter now fails with "web needs Node 26+ (running 22.14.0)" and the `nvm use` hint
  instead of dying inside undici. The reason is real, not stylistic — MSW 3 pulls undici 8,
  which binds `zlib.createZstdDecompress`, absent before Node 22.19; on 22.14 the vitest fork
  pool dies with "Cannot read properties of undefined (reading 'bind')" and reports **zero
  tests**, which reads as a broken suite. `pnpm dev` / `build` still run on older Node, since
  Next only needs 20.9.
- **Two `create-next-app` defaults removed:** `cacheComponents` and `partialPrefetching`.
  Neither is in the plan, both constrain how future pages may use dynamic APIs (suspense
  boundaries, no `dynamic = "force-dynamic"`), and no screen needs them. Adding them later
  is a one-line change per flag if a cache-heavy screen wants it.
- **No `next/font` in the skeleton.** The scaffold's Geist setup made `next build` depend on
  a Google Fonts fetch. WEB-01 introduces Inter + JetBrains Mono through `tokens.css` and
  `next/font` deliberately, with the fallback stack the plan already specifies.

**Trade-off accepted:** the web app builds and tests without network access to Google, at the
cost of a system-UI stack for the two packages until WEB-01 lands.

**Note on headers:** `next.config.ts` `headers()` applies to app routes but **not** to the
`/api/*` rewrite — verified: `/today` returns the full CSP/HSTS set, `/api/health` passes
through uvicorn's headers untouched. API responses therefore get their security headers from
Caddy (DP-03) and FastAPI (BE-01), not from the web app.
