# Tartib — Application Requirements

**Version:** 1.0 (design-complete draft)
**Date:** 22 November 2026
**Status:** Requirements frozen pending build. Changes must be made here before code.

Companion documents:
- `02-engine-spec.md` — the scheduling rules in implementation form
- `03-build-analysis.md` — server, cost and build-effort analysis
- `../mockups/` — 16 screens (web, mobile, wireframes), HTML sources included

---

## 1. Overview

A single-user scheduling application that turns a backlog of tasks, habits and prayer
obligations into a concrete, live calendar — and keeps it correct as reality changes.

It replaces ad-hoc, script-driven scheduling that has no interface, no persistence and no
visibility into its decisions.

The core insight driving every requirement below: **the scheduler is not the product — the
trust is.** A user who cannot see why a block moved will stop using the system and go back
to a manual calendar. Every automatic decision must therefore be explainable, reversible
and visible.

---

## 2. Goals

| # | Goal | Success measure |
|---|---|---|
| G1 | Never lose a task or a prayer | 100% of tasks are either scheduled, flagged, or in backlog — none silently dropped |
| G2 | Keep the calendar truthful | Every block in the app exists in Google Calendar within 60s of being accepted |
| G3 | Make common actions instant | Top 5 actions cost one gesture (§FR-14) |
| G4 | Explain every decision | Every automatic change is recorded with the rule that produced it |
| G5 | Respect the precedence hierarchy absolutely | No lower-ranked item ever displaces a higher one |
| G6 | Run without a personal machine | 24×7 on a server, no laptop dependency |
| G7 | Recover from total data loss | Full restore from Notion within 15 minutes |

## 3. Non-goals

Explicitly out of scope, and must not creep in:

- Meetings, scheduling links, attendee availability, team OOO, meeting prep
- Multi-user, teams, seats, RBAC, billing, sharing
- AI that decides the user's priorities
- Native iOS/Android apps (PWA only)
- Mobile browsers at 7-column week-grid density
- Importing from Todoist/Linear/Asana

---

## 4. User & context

Single user, one timezone (configurable; default Asia/Kolkata), one Google account, with an
optional work calendar attached read-only as the meetings feed.

Typical day: phone-first in the morning (what's next, tick habits), desktop in the evening
(plan the week, resolve flags). Notion is used for archival. Work and study tracks share the
same calendar alongside daily prayers and habits.

---

## 5. Definitions

- **Occurrence** — one scheduled instance of a habit (a weekly habit has one per week, a
  daily habit one per day). Streaks and skips count in occurrences, never in days.
- **Literal** — a fixed-time block: prayer, meeting, office hours, pinned block.
- **Flexible** — a block the engine may move: habit, task.
- **Qada** — a prayer that could not be placed in its window and is deferred to after Isha.
- **Flagged** — a task that could not be placed; it keeps a badge until resolved.
- **Pinned** — a block the user moved manually. The engine never touches it.
- **Compression / shrink** — reducing a habit's duration toward (never below) its minimum.

---

## 6. Global rules

**FR-1 — Precedence.** Strict hierarchy, highest wins:

1. Office meetings
2. Prayers
3. Office hours (High effort may not enter)
4. Pinned blocks
5. Habits
6. Tasks (by deadline pressure)
7. Backlog

*Acceptance:* for any conflict, the lower-ranked item is moved, compressed, or flagged —
never the higher. No code path may schedule a task onto a prayer or a meeting.

**FR-2 — Precedence is visible.** The hierarchy is displayed in the UI rail on every web
screen so the user can self-answer "why did that move?".

**FR-3 — Minimum chunk.** No block shorter than 30 minutes is ever created.

**FR-4 — Buffers.** After a High block: 15m. Medium: 10m. Low: 0m.

**FR-5 — Planning window.** 14 days rolling. Nothing is scheduled beyond it.

**FR-6 — Timezone.** All reads and writes in Asia/Kolkata, regardless of client timezone.

**FR-7 — Code-enforced invariants.** Three facts are physics, not preference, and are
enforced in code outside the settings table:

1. **No double-booking.** Two blocks may never occupy the same minute.
2. **A pending Qada block is never task-filled.**
3. **Only one plan version is active at a time.**

**The minimum chunk is NOT one of these** — it is a user setting (§SET-8), because 30m is a
working preference, not a law. Everything else in the engine, including the precedence order
itself, is data the user controls.

---

## 6A. Settings & configuration (SET)

**SET-0 — The governing rule: nothing requires a code edit.**
Every value the engine uses — precedence order, working hours, buffers, prayer times,
calendar routing, Google credentials, thresholds — is stored in the database, seeded from
defaults, and editable from the UI. **No scheduling constant may be hard-coded.** A build
that needs a code change to alter the plan is non-compliant, regardless of what it does.

**SET-1 — Google account connection, in-app.** OAuth start and completion from the settings
screen: connect, show granted scopes, show token health, re-authorize, disconnect. No CLI,
no terminal, no file editing. The redirect URI is configurable for self-hosting.

**SET-2 — Calendar discovery.** List every calendar on the connected account. Per calendar:
whether it is **read** (meetings feed), whether it may be **written**, its colour, and
whether its events are treated as busy or free.

**SET-3 — Calendar is a per-task field, not a gate.** Capture *infers* a calendar from the
task's subject using editable per-subject defaults (prayers → Prayers, cybersec and sys
design → Learnings, personal → Family, fun → Fun/Entertainment/Trips, Arabic → Arabic).
The user — or an external agent — may change the calendar on any task. The
defaults are conveniences, not a router.

*Acceptance:* a task with no calendar is **flagged and stays in inbox**; it is never written
to a guessed calendar. Calendar is shown in review next to Est and Priority (§UX-10).

**SET-4 — The calendars in use are preserved.** The user's existing structure (Prayers,
Learnings, Family, Fun/Entertainment/Trips, Arabic, Tasks & Todos) is represented as
routing rules, not as an assumption in code. Adding a new calendar is a UI action alone.

**SET-5 — Precedence is editable.** The seven ranks are reordered by drag. The UI **warns
when a reorder causes a prayer to yield to something below it**, and offers *Preview effect
on this week* before committing a change to the order.

**SET-6 — Prayer configuration.** Per prayer: fixed or computed, time, duration, window
start and end, protected edge minutes, notification lead. Plus Jummah-overrides-Friday,
calculation method, location, timezone, qada cap per day, and the qada placement rule
(after Isha only).

**SET-7 — Working hours.** Per-weekday office-hours windows, earliest schedulable block,
latest block end. Editable per day, not per week.

**SET-8 — Block rules.** Minimum chunk, buffers per effort level, planning window, auto-apply
policy for safe changes, ask-before-cross-day-moves, streak-break threshold, shrink mode.

**SET-9 — Habit defaults.** Default minimum duration, default compressible flag, default
window, default priority for new habits.

**SET-10 — Task defaults.** Default subject, default priority, and the inference rules used
by capture (which phrases set a deadline, what "high" maps to).

**SET-11 — Notifications.** Per-type enable and lead time (block starting, prayer/adhan,
plan needs approval, overload flag), quiet hours, delivery channel.

**SET-12 — Backup & restore.** Notion target page, mirror frequency, retention. A restore
action that runs a **dry-run diff first** and shows what would change before applying.

**SET-13 — Account & security.** Passkey or magic-link auth; active sessions with revoke.
Agent access is its own screen — see §15A for scoped tokens, auto-approve and attribution.

**SET-14 — Change safety.** Every settings change writes an audit entry (who, what, before,
after, when). Destructive actions — recompute the whole calendar, reset to defaults, delete
a habit, disconnect Google — each require an explicit confirm stating the consequence.

**SET-15 — Reset to defaults** per section, never globally in one click.

**SET-16 — Settings export/import** as JSON, for backup and migration to a new host.

**SET-17 — Field vocabularies.** The option lists that populate every manual form —
**subjects/tags, calendars, priorities, effort levels, split modes** — are stored data,
editable in Settings: add, rename, reorder, disable, remove. Changing a list changes the form
immediately with no deploy. Nothing about a field's possible values is hard-coded (§SET-0),
and nothing about them is guessed.

---

## 7. Prayers (PRY)

**PRY-1 — Times.** Fixed preferred times with a computed cross-check:

| Prayer | Time | Duration | Editable |
|---|---|---|---|
| Fajr | 05:15 | 30m | yes |
| Dhuhr | 13:00 | 30m | yes |
| Jummah (Fri only) | 12:45 | 60m | yes |
| Asr | 15:35 | 25m | yes |
| Maghrib | computed (~17:05) | 20m | computed |
| Isha | 19:45 | 45m | yes |

**PRY-2 — Windows.** Each prayer has a window. The **first and last 10 minutes of the
window are protected** and never usable. A prayer must fit entirely inside
`[start+10m, end−10m]`.

**PRY-3 — Collision with a meeting.** Shift the prayer within its protected core.
*Acceptance:* prayer at 13:00, meeting 13:00–13:15, window 13:00–14:00 → prayer moves to
13:20, not to 13:15.

**PRY-4 — Qada.** If the prayer cannot fit in its core at all, defer to **after Isha,
never before**. Multiple qadas stack after Isha; order is irrelevant.

**PRY-5 — Qada is protected.** While pending, no task and no habit may occupy a qada
block. Only the user may clear it (mark prayed, or move it and mark prayed).

**PRY-6 — Early completion releases time.** When a qada is marked prayed early, the
remaining time returns to normal capacity. Freed capacity is refilled by flagged tasks
first, then by deadline pressure.

**PRY-7 — Invariants.** A prayer never moves for a habit, task, pinned block or deadline.
Tasks never overlap a prayer or qada block.

**PRY-8 — Drift guard.** If the computed time differs from the reference (AlAdhan) value by more than
10 minutes, raise a flag in the app. Never silently move the evening.

---

## 8. Office hours & meetings (OFF)

**OFF-1 — Office hours** are a configurable window (default 10:00–18:30, Mon–Fri).
High-effort work may not be scheduled inside it; Medium and Low may use gaps.

**OFF-2 — Meetings** are imported read-only from Google Calendar and rendered as literal
blocks. They outrank everything, including prayers.

**OFF-3 — Office hours are immutable** to "make time" suggestions. The engine may propose
extending the day's edge, never editing office hours.

---

## 9. Habits (HAB)

**HAB-1 — Model.** Name, weekday set, ideal duration, minimum duration, window
(not-before / not-after), ideal time, priority, compressible flag.

**HAB-2 — Hard habits.** Where `min == ideal` the habit is never compressed (e.g.
Qur'an 15m). If a hard habit is the only blocker, the task flags — the engine never asks
to override the habit.

**HAB-3 — Shrink is minimal.**

```
shortfall = task_need − free_capacity_before_deadline
flex      = habit_ideal − habit_min
shrink    = min(shortfall, flex)
```

Shrink by exactly what is needed. If 30m suffices, shrink 30m — never a percentage and
never a fixed ladder. If the shortfall exceeds the flex, take the whole flex, schedule
what fits, and flag the remainder.
*Acceptance:* task needs 45m, habit is 3h with 60m min → habit shrinks to 2h 15m, not to 60m.

**HAB-4 — Floor is absolute.** Never compress below `min`.

**HAB-5 — Daily reset.** Compression resets each occurrence. Compression counts are
recorded for display only and never degrade the base duration.

**HAB-6 — Skip semantics (three actions).**

| Action | Reach | Streak effect | Blocks |
|---|---|---|---|
| Skip (one tap) | This occurrence | Counts as a skipped occurrence | Released immediately |
| Skip until… (long-press) | User-picked span | Every occurrence in the span counts as skipped | Released for the span |
| Delete | Permanent | Ends the habit; nothing is marked missed | All future blocks removed |

**HAB-7 — Streak break: three consecutive skipped occurrences, per habit.**
Counting is per **habit occurrence**, never per calendar day. A weekly habit breaks after
three skipped weeks, not three days.

- 1 skipped occurrence → streak holds
- 2 consecutive → streak holds, card warns "one more ends it"
- 3 consecutive → **streak resets to 0**, habit marked **ended**
- Logging the habit at any point resets the counter to zero

**HAB-8 — Skipping is not free.** "Skip until…" counts toward the break. There is no
exemption for long pauses: the cost of pausing is the loss of the streak, deliberately.
*Rationale (user):* "it prevents me from using it too often and shows me that skip is not
free, it costs me my consistency."

**HAB-8a — Warn at the moment of choosing.** Because a long skip span will itself end the
streak, the skip-until picker must state the consequence before confirming:
*"3 occurrences fall in this span — this will end your 14-day streak on Thu 26."*
A pause that silently kills a streak is a trap, not a penalty.

**HAB-8b — Task deferral is free.** Deferring a *task* to a date carries no penalty and no
streak concept. The two "skip until" actions are deliberately asymmetric: habits pay,
tasks do not.

**HAB-9 — Misses.** A day passing with the occurrence neither logged nor skipped breaks
the streak immediately.

**HAB-10 — Reactivate.** An ended habit can be reactivated from its card. The streak
restarts at **0**; all past data is retained (occurrences, best streak, compression count)
and remains visible in Insights. The chart shows a gap, never a blank line.

**HAB-11 — Delete keeps history.** Deleting archives the record under "Ended <date>".
Nothing is recorded as missed, because a deleted habit has no occurrences.

**HAB-12 — Skip shows its payoff.** Every skip displays what the freed time enables
("frees 18:30 → W2D2 can start today").

---

## 10. Tasks (TSK)

**TSK-1 — Fields.** Title, estimate, priority, deadline, effort (High/Med/Low), split
(Atomic / Subtasks / Auto), subtasks with weighted minutes summing to the estimate,
depends-on, min chunk, subject, **calendar**.

"Task" is the umbrella term. Project work is not a separate entity — a five-hour allocation
for a project is simply a task whose **subject** is that project, split into chunks by the
existing engine. No new object type, no separate screen.

**TSK-2 — Scheduling gates.** A task cannot be scheduled when: no estimate, no priority,
dependency incomplete, no qualifying slot before deadline, or blocked by a pinned conflict.
The reason is always surfaced in the UI.

**TSK-3 — States.** inbox → scheduled → in progress → partial → done / skipped, plus
backlog (never scheduled).

**TSK-4 — Partial progress.** Logging "45m of 90m" returns the remainder to the pool,
re-chunked to ≥30m.

**TSK-5 — Partial scheduling.** When a task cannot fully fit:
1. Schedule the amount that fits — do not hold it back
2. Flag the remainder (it crosses the deadline)
3. When time is freed, reschedule to bring the task to full
4. If time never opens, split the remainder into later free time, keeping its flag

*Acceptance:* 3h 30m task with 3h available → 3h placed, 30m flagged. User skips a habit
freeing 60m → the 30m is scheduled and the flag clears.

**TSK-6 — Defer / snooze.** A task can be deferred until a date ("skip until" for tasks).
Deferring moves no deadline unless the user says so, and is recorded in history.
Deferring is never penalised — streaks are a habit concept only.

**TSK-7 — Dependencies.** A task never schedules before its dependencies complete. Chains
propagate: a blocked dependency blocks dependents and shows the chain.

**TSK-8 — Subtasks.** Weights sum to the estimate. Completing a subset reduces the
remaining estimate proportionally. The UI shows a segmented progress bar, not one bar.

**TSK-9 — Recurring tasks** are distinct from habits: work that must happen N times, not a
routine to defend. They are not subject to compression.

---

## 11. Planning engine (ENG)

**ENG-1 — Resolution order** for each unscheduled task, in deadline order:
1. Free slot satisfying gates, buffers, min chunk
2. Free slot on an earlier day within the plan window
3. Shrink a habit — minimal, last resort, only the deadline-critical blocker
4. Flag and stop

Shrinking is never the first move.

**ENG-2 — Dry run always.** The engine never writes to Google Calendar directly. It
produces a diff; the user accepts.

**ENG-3 — Pin on move.** Any block the user drags becomes user-owned and is never moved by
the engine again, until unpinned.

**ENG-4 — Idempotence.** Running the planner twice with unchanged inputs produces an empty
diff.

**ENG-5 — Pre-clean.** Before planning, remove stale engine-created blocks so the plan
reflects reality rather than history.

---

## 12. Re-plan & approval (RPL)

**RPL-1 — Triggers.** Hourly, on task change, on calendar change, on manual request.

**RPL-2 — Diff.** Every change is presented with from → to, the rule applied, and a
one-line reason.

**RPL-3 — Classification.**
- **Safe (auto-apply allowed):** move within the same day; shrink a habit to fit
- **Must ask:** move across days; drop or skip anything; push a deadline
- **Never:** modify a pinned block

**RPL-4 — Nothing writes without acceptance.** Except changes classified Safe, where the
user has explicitly enabled auto-apply.

**RPL-5 — Failure path.** GCal write fails → retry once → roll back the diff → alert.
Never leave a half-applied plan.

**RPL-6 — History.** Every applied change is written to the engine log with its rule.

---

## 13. Overload (OVL)

**OVL-1 — Flag and stop.** When required capacity exceeds available, the engine stops and
reports the exact shortfall. It never overbooks.

**OVL-2 — Levers offered, never chosen:**
push to next week (deadline moves with it) · skip a habit occurrence · make time (extend
the day's edge) · reduce the task (drop a subtask).

**OVL-3 — If ignored.** The task keeps its flag and badge; exactly one reminder the next
morning — never hourly.

---

## 14. Interaction requirements (UX)

**UX-1 — One gesture for the top five:** tick habit · skip habit · log +15m on the current
block · capture a task · accept the plan.

**UX-2 — Undo beats confirm.** 10-second undo toast on everything reversible.

**UX-3 — Only two hard confirms exist:** applying the plan to Google Calendar, and deleting
a habit.

**UX-4 — Tap is the obvious action, long-press the alternative.**

**UX-5 — Infer, don't ask.** Estimate from the last similar task, priority from subject,
deadline from "before Fri".

**UX-6 — Every skip/compression shows its consequence inline.**

**UX-7 — Mobile week view is an agenda list.** No 7-column grid below 768px.

**UX-8 — Noise budget: four notifications only.** Block starting · prayer time · plan needs
approval · overload flag.

**UX-9 — Density over whitespace.** This is a tool used 10× daily, not a marketing page.

---

## 15. Capture & bulk (CAP)

**CAP-1 — Natural-language capture.** One line ("2h DBMS revision before friday, high")
parses into estimate, priority, deadline, subject. Parsed values appear as **editable chips**
before saving.

**CAP-2 — Nothing schedules without estimate + priority.** Missing values leave the task in
inbox with the reason shown.

**CAP-3 — Bulk create.** Paste a syllabus, list or chat dump. A parse table shows
`rows found / confident / needs a duration / dependencies`, with per-row edits before commit.

**UX-10 — Review shows Est, Priority and Calendar.** Every path that creates tasks — NL
capture, bulk import, agent import — lands on a review table where those three fields are
visible and editable per row. Rows missing any of the three are grouped as *needs a decision*
and stay in inbox. Nothing is created until the user commits.

**CAP-4 — Agent parity.** An external agent uses the *same* endpoint and dry-run as
the UI. A bulk import from chat must be reviewable in-app and vice versa.

**CAP-5 — Manual entry is entirely local.** Filling the form by hand invokes no model, not
even for "smart" suggestions. Every field is populated from the user-maintained vocabularies
(§SET-17), the user's own last-used values, or what they type. Consequences that must hold:
instant response, works offline, zero token cost, and identical behaviour every time.

**CAP-6 — The form is fast by default.** Three fields visible (title, estimate, priority);
the rest collapsed behind a disclosure. Keyboard-complete: Tab order follows reading order,
`Enter` saves, `⌘/Ctrl+Enter` saves and schedules. Last-used subject and calendar are
remembered and pre-selected. Validation is inline — never a modal, never a blocking dialog.

**CAP-7 — AI is confined to one path.** Natural-language capture is the *only* place a model
is used, it is triggered by an explicit action (submit a free-text line), and it is optional.
Typing into the form never triggers it. A user who never uses NL capture gets a product with
zero AI dependency.

**CAP-8 — AI output lands in the same form.** Whatever NL capture produces is written into the
manual form's fields for review and editing — same component, same rules. Nothing is created
directly from a model response, and the user can always finish the job by hand instead.

---

## 15A. Agent access & provenance (AGT)

The application must let an external agent (e.g. a personal AI assistant) create, edit and move tasks — singly or in bulk (a whole
course in one call) — **without a human in the loop for every action**, while making it
unmistakable which changes were not made by the user.

**AGT-1 — Parity.** The agent API uses the same endpoints, validation and engine as the UI.
No second code path, no reduced rules: an agent-created task obeys precedence, gates and
buffers identically.

**AGT-2 — Independently scoped permissions.** Each may be granted or withheld on its own:
read · create tasks · edit task fields · move/reschedule blocks · **apply plan to Google
Calendar**.

**AGT-3 — Two categories are never grantable.** Deleting tasks, editing habits, and changing
settings are permanently unavailable to every token.

**AGT-4 — Auto-approve is per permission, never global.** Typical grant: create/edit/move ON,
apply-plan OFF. The agent may therefore write tasks and shift blocks freely but must return
a proposal for anything that reaches the calendar.

**AGT-5 — Bulk operations.** Batch create/edit is a first-class endpoint: single call, up to
a configured batch maximum, with a per-row result (`created / rejected + reason`). A partial
failure never rolls back the rows that succeeded.

**AGT-6 — Attribution is data, not a log.** Every task, placement and history entry stores
`actor` (`user` | `agent:<token-name>`), `auto_approved` (bool) and the timestamp. This is a
column on the record, so it survives log rotation and restore.

**AGT-7 — Visual markers.** Agent-created or agent-modified items carry an **AI** marker;
changes that were applied without asking carry an **AUTO** marker. Both appear in the task
list, the task detail, the task's history, and the engine log. A dispatched user action is
never shown as AI.

**AGT-8 — Filterable.** The task list filters by *created by agent*, *auto-approved*, or
*created by me*, and the engine log filters by actor.

**AGT-9 — Revocation is forward-only.** Revoking a token stops future actions; past actions
keep their markers unchanged. Available at all times from Agent access.

**AGT-10 — Limits.** Per-token rate limit, daily cap and batch maximum, all editable.

**AGT-11 — Review remains available, not mandatory.** Because auto-approve exists, the
review table (§UX-10) becomes the *default* surface for bulk imports but not a required gate.
A token with create permission writes directly; the rows still land in the task list marked
**AI**, still flagged if Est / Priority / Calendar is missing.

---

## 16. Calendar sync (CAL)

**CAL-1 — Google Calendar** is the display layer. Blocks the app creates are written to
designated calendars (Tasks & Todos, Prayers, etc.).

**CAL-2 — Ownership markers.** The app must be able to identify its own events to avoid
duplication and to clean stale ones, without touching user-created events.

**CAL-3 — Two-way awareness.** External calendar changes trigger a re-plan; a block the
user moved in Google Calendar is treated as pinned.

**CAL-4 — Latency.** Accepted changes appear in Google Calendar within 60 seconds.

---

## 17. Notion backup (NOT)

**NOT-1 — Bookkeeper only.** Postgres is the source of truth. Notion is never read during
normal scheduling.

**NOT-2 — Write-only mirror** after every plan application. Fields: title, estimate,
priority, deadline, effort, split, subtasks, depends-on, placement history.

**NOT-3 — Restore path.** Snapshot → diff vs Notion → rehydrate → re-plan once → review delta.

**NOT-4 — Target.** Full restore from Notion within 15 minutes of data loss.

---

## 18. Insights (INS)

**INS-1 — Adherence:** planned vs actually completed, per week.
**INS-2 — Habit consistency:** per-habit streak calendar, distinguishing full / compressed /
skipped / missed.
**INS-3 — Subject split:** where the week went, by subject.
**INS-4 — Debt:** backlog size and overdue trend.
**INS-5 — Compressions:** count per habit per week — the early warning that a habit is
being eroded.

---

## 19. Data model (summary)

```
habit        id, name, weekdays[], ideal_min, min_min, window_start, window_end,
             ideal_time, priority, compressible, state(active|paused|ended),
             created_at, ended_at, archive_ref
occurrence   id, habit_id, date, planned_min, actual_min, state
             (scheduled|done|skipped|missed|compressed), skip_run
task         id, title, est_min, priority, deadline, effort, split, subject,
             state(inbox|scheduled|in_progress|partial|done|skipped|backlog|flagged),
             depends_on[], flag_reason, deferred_until
subtask      id, task_id, name, weight_min, done
placement    id, ref_type, ref_id, calendar_event_id, start, end, owner
             (engine|user), pinned, created_at
prayer       id, name, date, window_start, window_end, block_start, block_end,
             state(normal|shifted|qada|prayed), qada_index
plan_run     id, started_at, trigger, diff_json, accepted_at, applied_at
engine_log   id, ts, rule, subject, effect, undoable
```

---

## 20. API surface (minimum)

```
GET    /api/today
GET    /api/week?from=
GET    /api/tasks?state=
POST   /api/tasks                 capture (NL or structured)
PATCH  /api/tasks/:id
POST   /api/tasks/:id/progress
POST   /api/tasks/:id/defer
POST   /api/tasks/bulk            parse / preview / commit
GET    /api/habits
POST   /api/habits
PATCH  /api/habits/:id
POST   /api/habits/:id/skip       {scope: today | until, until?}
POST   /api/habits/:id/reactivate
GET    /api/prayers?date=
POST   /api/prayers/:id/prayed
GET    /api/plan/diff             dry run
POST   /api/plan/apply            {accept: [changes]}
GET    /api/log                   engine log, filterable
GET    /api/insights?range=
POST   /api/sync/calendar
POST   /api/backup/notion
POST   /api/restore/notion        {snapshot, dry_run}
```

---

## 21. Non-functional requirements

**NFR-1 — Hosting.** Single VPS, Docker Compose (API, worker, Postgres, Caddy).
**NFR-2 — Cost ceiling.** ≤ $8/month all-in for a single user.
**NFR-3 — Reliability.** Scheduled runs fire within 5 minutes of schedule. A missed run
raises an alert; three consecutive misses raise it louder.
**NFR-4 — Watchdog.** Heartbeat + external check. A dead box must alert, not fail silently
— a scheduler that silently stops is the failure mode this requirement exists to prevent.
**NFR-5 — Backups.** Nightly snapshot off-box, 14-day retention.
**NFR-6 — Security.** Single user, passkey or magic-link auth, TLS everywhere, secrets in
env only, Google refresh token encrypted at rest.
**NFR-7 — Performance.** Today/Week render in <300ms from a warm cache; plan run <2s.
**NFR-8 — Offline.** PWA serves a cached read-only view; writes queue and replay.
**NFR-9 — Timezone/DST.** Asia/Kolkata has no DST, but all arithmetic must be timezone-aware.

**NFR-10 — Resource isolation.** The scheduler stack must run with a hard memory cap
(recommended 1 GB total) and must be unaffected by resource pressure from co-hosted
applications. A co-tenant out-of-memory kill must never interrupt prayer scheduling or a
calendar write. The host may run other applications, so this is a real constraint, not a
theoretical one.

**NFR-11 — Deployment shape.** The application must run standalone on a single VPS with no
dependency on a personal machine. An external agent is an optional client, never a runtime
requirement; a lightweight Discord integration must be possible without hosting a full agent.

---

## 22. Screen inventory

| # | Screen | Platform | Mockup |
|---|---|---|---|
| 1 | Today | web + mobile | `web/01`, `mobile/01` |
| 2 | Week (grid / agenda) | web + mobile | `web/05`, `mobile/01` |
| 3 | Tasks + bulk create | web | `web/01` |
| 4 | Task detail + placement explainer | web | `web/02` |
| 5 | Habits + compression rule | web | `web/01` |
| 6 | Prayers | web + mobile | `web/02`, `mobile/01` |
| 7 | Insights | web | `web/02` |
| 8 | Engine log | web | `web/03` |
| 9 | Re-plan review | web + mobile | `web/06`, `mobile/02` |
| 10 | Interaction budget | web (spec) | `web/04` |
| 11 | Prayer conflict + skip | mobile | `mobile/02` |
| 12 | Delete habit + partial task | mobile | `mobile/03` |
| 13 | Streak states + reactivate | mobile | `mobile/04` |
| 14 | Structural wireframes (9 flows) | both | `wireframes/01` |
| 15 | Settings — Google, precedence, calendars | web | `web/07` |
| 16 | Settings — block rules / engine constants | web | `web/07` |
| 17 | Review import (Est + Priority + Calendar) | web | `web/08` |
| 18 | Agent access — scopes, auto-approve, activity | web | `web/09` |
| 19 | AI / AUTO markers in the task list | web | `web/09` |

---

## 23. Acceptance scenarios

**A1 — Prayer vs meeting.** Dhuhr 13:00–14:00; meeting 13:00–13:15.
→ Prayer moves to 13:20. No qada. Log records "shifted, 10m edges kept".

**A2 — Total prayer block.** Window fully booked.
→ Qada placed after Isha. Block is dashed, task-proof. Log records stacking order.

**A3 — Minimal shrink.** Task 45m, habit 3h with 60m min, only slot available.
→ Habit becomes 2h 15m. Not 60m. Log records "gave 45m, not more".

**A4 — Shrink to floor + flag.** Task 3h 30m, capacity 1h, habit flex 2h.
→ Habit goes to 60m, 3h scheduled, 30m flagged.

**A5 — Skip then free.** As A4, user then skips the habit.
→ Remaining 30m schedules; flag clears.

**A6 — Three skips.** Same habit skipped three occurrences (days apart if weekly).
→ Third skip ends streak at 0; card shows Reactivate; history preserved.

**A7 — Skip until costs the streak.** "Skip until next week" on a daily habit.
→ Occurrences within the span count as skipped; the streak breaks at the third one.

**A8 — Overload ignored.** Thu over-committed by 1h 30m, user acts on nothing.
→ Task keeps flag, badge on Today, exactly one reminder next morning.

**A9 — Pinned block.** User drags a task to Tue 21:00.
→ Subsequent plans never move it; log shows "pinned, engine left alone".

**A10 — Notion restore.** DB deleted.
→ Restore produces the same task/habit set; one re-plan reproduces an equivalent calendar.

---

## 24. Open questions

None. All rules are frozen as of 22 November 2026.

Two decisions worth remembering because they were deliberately chosen against the easier
option:
- **Skip is not free.** Multi-day pauses count toward the break, by design.
- **Streaks are per occurrence, not per day.** A weekly habit must miss three weeks, not
  three days.
