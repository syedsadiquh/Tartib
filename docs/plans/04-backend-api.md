# 04 — Backend Services & HTTP API

FastAPI app in `backend/src/scheduler/api/`. Every route is under `/api`. Every route declares
`response_model` so the OpenAPI → TypeScript generation (`make gen-api`) is complete. Routers
are thin: parse → call one service function → return DTO.

## 0. Cross-cutting

### 0.1 Auth & actor resolution (`api/deps.py`)
```python
def get_actor(request) -> ActorContext:
    # 1. Authorization: Bearer sch_… → agent token (BE-21). actor = "agent:<name>".
    #    auto_approved is decided per action by the service (scope ∈ token.auto_approve).
    # 2. Cookie "sid" → auth_session (sliding expiry). actor = "user".
    # 3. Otherwise 401 UNAUTHENTICATED.
def require_scope(scope: str)  # dependency; users pass all scopes; agents need scope ∈ token.scopes
```
Never-grantable (AGT-3): routes for task delete, habit create/edit/delete, settings, vocab,
google, agent tokens, auth, backup/restore are **user-only** → agent gets 403
`FORBIDDEN_SCOPE` regardless of token.

CSRF: cookie is `HttpOnly; Secure; SameSite=Lax`; all non-GET requests from cookie sessions must
carry header `X-Requested-With: tartib` (the web client always sends it). Reject otherwise
(403 `CSRF`).

### 0.2 Common headers
- `Idempotency-Key` (optional on any POST/PATCH/DELETE): if present and seen within 48 h for the
  same method+path, return the stored response (NFR-8 offline replay).
- Responses of reversible mutations include `"undo": {"token": "...", "label": "Skipped Gym today", "expires_at": "…"}`.

### 0.3 Post-mutation hooks
Every service mutation that changes schedulable inputs — **every** one, D-29 — calls
`jobs.enqueue_replan(trigger, debounce=settings.block_rules.replan_debounce_sec, released=[…])`
(dedupe key `replan`; default debounce 2 s). Triggers: `task_change`, `skip`, `prayed`,
`settings`, `agent`, `pin`, `calendar_change`. `released` lists the intervals the action freed
(habit skip, prayed early, task done/skipped/deferred, block deleted). When jobs coalesce,
released lists are concatenated (D-14 rule 6). Typical edit-to-Google latency is ~3–6 s.

### 0.4 DTO conventions
- Response DTOs in `schemas/*.py`, suffix `Out`; request bodies suffix `In`/`Patch`.
- Times ISO with offset in the settings tz. Durations `*_min` ints.
- **Grid validation (D-26):** `est_min`, subtask `weight_min`, habit `ideal_min`/`min_min`, progress
  `minutes` must be > 0 and multiples of `block_rules.slot_granularity_min` → else 422
  `NOT_ON_GRID` with the nearest valid values in `details`. (The engine also rounds up defensively.)

### 0.5 Shared DTOs (`schemas/common.py`)
```python
class FlagOut(BaseModel):
    code: str; title: str; detail: str
    needed_min: int | None; placed_min: int | None; short_min: int | None
    available_before_shrink_min: int | None; shrink_gained_min: int | None
    deadline: datetime | None; levers: list[str]; blocked_by: list[UUID]
    raised_at: datetime | None
class PlacementBrief(BaseModel):
    id: UUID; kind: str; start: datetime; end: datetime; minutes: int
    calendar_id: UUID; calendar_color: str; pinned: bool; chunk_index: int | None; chunk_count: int | None
class SubtaskOut(BaseModel):
    id: UUID; name: str; weight_min: int; sort: int; done: bool; dropped: bool
class DepOut(BaseModel):
    id: UUID; title: str; state: str; fully_placed: bool
class UndoOut(BaseModel):
    token: str; label: str; expires_at: datetime
```
- Lists are `{"items": [...], "next_cursor": "…|null"}` where paginated.

---

## 1. Endpoint catalogue

Legend: **U** = user only · **A:scope** = agents with that scope (users always allowed).

| Method & path | Who | Package |
|---|---|---|
| `GET /api/health` · `GET /api/health/ready` | public | F-02, WK-05 |
| `GET /api/version` | A:read | BE-27 |
| `POST /api/google/webhook` | Google (channel token) | IN-15 |
| `POST /api/auth/magic-link` · `GET /api/auth/magic-link/verify` | public | BE-03 |
| `POST /api/auth/passkey/{register,login}/{options,verify}` | U / public(login) | BE-04 |
| `GET /api/auth/passkeys` · `DELETE /api/auth/passkeys/{id}` · `PATCH /api/auth/me {display_name}` | U | BE-04 |
| `GET /api/auth/me` · `POST /api/auth/logout` · `GET /api/auth/sessions` · `DELETE /api/auth/sessions/{id}` | U | BE-03 |
| `GET /api/today` | A:read | BE-17 |
| `GET /api/week?from=YYYY-MM-DD` | A:read | BE-17 |
| `GET /api/tasks` · `GET /api/tasks/{id}` | A:read | BE-07 |
| `POST /api/tasks` | A:tasks.create | BE-07 |
| `PATCH /api/tasks/{id}` | A:tasks.edit | BE-07 |
| `DELETE /api/tasks/{id}` | U | BE-07 |
| `POST /api/tasks/{id}/progress` | A:tasks.edit | BE-09 |
| `POST /api/tasks/{id}/defer` | A:tasks.edit | BE-09 |
| `POST /api/tasks/{id}/state` (done / skip / backlog / reopen) | A:tasks.edit | BE-09 |
| `POST /api/tasks/bulk` (parse · commit) | A:tasks.create | BE-22 |
| `POST /api/capture/parse` | A:tasks.create | BE-22 |
| `GET /api/import-batches/{id}` · `PATCH …/{id}/rows/{row}` · `POST …/{id}/commit` · `POST …/{id}/discard` | A:tasks.create | BE-22 |
| `GET /api/habits` · `GET /api/habits/{id}` | A:read | BE-10 |
| `POST /api/habits` · `PATCH /api/habits/{id}` · `DELETE /api/habits/{id}` | U | BE-10 |
| `POST /api/habits/{id}/log` | U | BE-11 |
| `POST /api/habits/{id}/skip` · `GET /api/habits/{id}/skip-preview` | U | BE-11 |
| `POST /api/habits/{id}/reactivate` | U | BE-11 |
| `GET /api/prayers?date=` · `GET /api/prayers/week?from=` | A:read | BE-12 |
| `POST /api/prayers/{instance_id}/prayed` · `POST /api/prayers/{instance_id}/move` | U | BE-12 |
| `GET /api/placements/{id}` (block drawer: why, history, actions) | A:read | BE-15 |
| `POST /api/placements` (user-created block: tray drag / log past work) | A:blocks.move | BE-15 |
| `POST /api/placements/{id}/move` (drag = pin) | A:blocks.move | BE-15 |
| `POST /api/placements/{id}/unpin` | A:blocks.move | BE-15 |
| `POST /api/placements/{id}/progress` (+15m on current block) | U | BE-15 |
| `POST /api/plan/run` | A:read (dry run only) | BE-13 |
| `GET /api/plan/current` · `GET /api/plan/diff` (alias: run if none) | A:read | BE-13 |
| `POST /api/plan/apply` | A:plan.apply | BE-14 |
| `POST /api/plan/reject` | U | BE-13 |
| `GET /api/plan/runs` | A:read | BE-13 |
| `GET /api/decisions` · `GET /api/decisions/{task_id}/levers` · `POST /api/decisions/{task_id}/lever` | U | BE-16 |
| `GET /api/log` | A:read | BE-18 |
| `GET /api/activity?entity_type=&entity_id=` | A:read | BE-18 |
| `GET /api/insights?range=week|month&from=` | A:read | BE-23 |
| `GET /api/settings` · `PATCH /api/settings/{section}` · `POST /api/settings/{section}/reset` | U | BE-19 |
| `GET /api/settings/export` · `POST /api/settings/import` | U | BE-19 |
| `POST /api/settings/precedence/preview` | U | BE-19 |
| `GET/POST /api/vocab/{kind}` · `PATCH/DELETE /api/vocab/{kind}/{id}` · `POST /api/vocab/{kind}/reorder` | U | BE-20 |
| `GET /api/audit` | U | BE-19 |
| `GET /api/google/status` · `POST /api/google/connect` · `GET /api/google/callback` · `POST /api/google/disconnect` | U | IN-02 |
| `GET /api/calendars` · `PATCH /api/calendars/{id}` · `POST /api/calendars/discover` | U (GET: A:read) | IN-03 |
| `POST /api/sync/calendar` | U | IN-05 |
| `GET/POST /api/agent/tokens` · `PATCH /api/agent/tokens/{id}` · `POST /api/agent/tokens/{id}/revoke` | U | BE-21 |
| `GET /api/agent/activity` · `GET /api/agent/proposals` · `POST /api/agent/proposals/{id}/{approve|reject}` | U | BE-21 |
| `GET /api/day-overrides` · `PUT /api/day-overrides/{date}` · `DELETE …` | U | BE-16 |
| `POST /api/backup/notion` · `GET /api/backup/status` · `POST /api/restore/notion` | U | IN-08/09 |
| `GET /api/push/vapid-key` · `POST /api/push/subscribe` · `DELETE /api/push/subscribe` · `POST /api/push/test` | U | IN-10 |
| `GET /api/onboarding/state` · `POST /api/onboarding/step` · `GET /api/onboarding/habit-suggestions` | U | BE-25 |
| `POST /api/undo/{token}` | same actor as original | BE-06 |

---

## 2. Work packages

### BE-01 — App factory, error handling, request ids
**Depends on:** DB-02 **Size:** S
**Files:** `api/app.py`, `api/errors.py`, `api/middleware.py`
**Steps:**
1. `create_app()` registers routers, middleware, exception handlers. Startup: check Alembic head
   (`alembic.runtime` compare) → refuse to start if DB is behind; run seeder.
2. `DomainError(code, message, status, details)` base + subclasses `NotFound`, `Conflict`,
   `Unprocessable`, `Forbidden`. Handler renders the JSON error shape (01-architecture §4).
   Pydantic `RequestValidationError` → 400 `VALIDATION_ERROR`.
3. Middleware: `X-Request-Id` (generate if absent), structured access log, timing.
**Tests:** unknown route → 404 JSON shape; validation error shape; request id echoed.

### BE-02 — Actor context, attribution, activity & audit writers
**Depends on:** BE-01 **Size:** S
**Files:** `services/actor.py`, `services/activity.py`, `services/audit.py`
**Steps:**
1. `ActorContext` dataclass (`actor`, `auto_approved`, `token_id`, `is_agent` property).
2. `activity.record(session, actor, entity_type, entity_id, kind, summary, data)`.
3. `audit.record(session, actor, area, action, before, after)`.
4. Helper `stamp(obj, actor, created=False)` sets the attribution columns.
**Tests:** stamp on create vs update; agent actor string format.

### BE-03 — Sessions & magic link
**Depends on:** BE-02, IN-13 **Size:** M
**Spec:** SET-13, NFR-6, D-23
**Files:** `auth/sessions.py`, `auth/magic_link.py`, `api/routers/auth.py`, `cli.py login-link`
**Steps:**
1. `POST /api/auth/magic-link {email}` → if email == owner, create 32-byte token, store hash,
   email link `APP_BASE_URL/api/auth/magic-link/verify?token=…` (IN-13). Always return 202
   (don't reveal whether the email matched). Rate-limit 5/hour.
2. `GET …/verify?token=` → valid & unused & unexpired → mark used, create session, set cookie
   `sid` (30 days, sliding: refresh `expires_at` when `last_seen_at` older than 1 day), redirect `/`.
3. `scheduler-cli login-link` prints a fresh link (same mechanism, bypasses email).
4. `GET /api/auth/me` → `{email, display_name, has_passkey, google_connected}`.
5. Sessions list/revoke; logout revokes current.
**Tests:** reused token rejected; expired rejected; cookie flags; revoked session → 401.

### BE-04 — Passkeys (WebAuthn)
**Depends on:** BE-03 **Size:** M
**Files:** `auth/passkey.py`, routes in `routers/auth.py`
**Also:** `GET /api/auth/passkeys` (id, name, created_at, last_used_at), `DELETE /api/auth/passkeys/{id}`
(refuse deleting the last passkey only if no email/SMTP login is possible — 409 `LAST_LOGIN_METHOD`),
`PATCH /api/auth/me {display_name}`.
**Steps:** use `webauthn` library. RP id = host of `APP_BASE_URL`, origin = `APP_BASE_URL`.
Registration requires an existing session. Store challenge in a signed short-lived cookie
(`webauthn_challenge`, 5 min). Login: `options` (allowCredentials = all stored) → `verify` →
update sign_count → create session.
**Tests:** use library test vectors or mock verification functions; ensure challenge mismatch → 400.

### BE-05 — Settings service (read side)
**Depends on:** DB-02 **Size:** S
**Files:** `services/settings.py`
**Steps:** `get_settings(session) -> AppSettings` (validated); `engine_settings(app) -> EngineSettings`
(projection used by the snapshot builder); per-request memo.
**Tests:** projection maps every field; invalid JSON in a section raises a clear error naming the section.

### BE-06 — Undo & idempotency
**Depends on:** BE-02 **Size:** M
**Spec:** UX-2, NFR-8, D-22
**Files:** `services/undo.py`, `api/routers/undo.py`, `api/middleware.py` (idempotency)
**Steps:**
1. `undo.register(session, actor, kind, inverse: dict, label) -> UndoOut` (token, 15 s expiry).
2. A registry maps `inverse["service"]` strings to callables, e.g. `"habits.unskip"`,
   `"tasks.unprogress"`, `"tasks.undefer"`, `"tasks.set_state"`, `"placements.restore"`.
3. `POST /api/undo/{token}` → same actor, unexpired, unused → run inverse, mark used, enqueue replan.
4. Idempotency middleware: for mutating requests with `Idempotency-Key`, look up; if found,
   return stored response; else run and store (status + body) when status < 500.
**Tests:** undo after expiry → 410 `UNDO_EXPIRED`; idempotent replay returns identical body without double effect.

### BE-07 — Tasks CRUD + validation + gates
**Depends on:** BE-05, BE-02 **Size:** L
**Spec:** TSK-1, TSK-2, TSK-3, SET-3, CAP-2, AGT-1, AGT-6..8
**Files:** `schemas/tasks.py`, `services/tasks.py`, `api/routers/tasks.py`
**DTOs:**
```python
class SubtaskIn(BaseModel): id: UUID | None; name: str; weight_min: int; done: bool = False
class TaskIn(BaseModel):
    title: str
    est_min: int | None = None          # multiple of slot granularity (validate in service)
    priority_key: str | None = None
    deadline: datetime | None = None
    effort_key: str | None = None
    split_key: str | None = None        # default task_defaults.split_key
    subject_key: str | None = None
    calendar_id: UUID | None = None     # if None and subject has default calendar → inferred=True
    min_chunk_min: int | None = None
    depends_on: list[UUID] = []
    subtasks: list[SubtaskIn] = []
    notes: str = ""
    deferred_until: date | None = None
    recurrence: RecurrenceIn | None = None   # BE-24
    state: Literal["inbox","backlog"] = "inbox"
class TaskPatch(TaskIn): all fields optional (use model with every field Optional + exclude_unset)
class TaskOut(BaseModel):
    id, title, notes, est_min, priority_key, deadline, effort_key, split_key, subject_key,
    calendar_id, calendar_inferred, min_chunk_min, state, logged_min, remaining_min,
    deferred_until, flag: FlagOut | None, gates: list[str],  # e.g. ["missing_estimate"]
    subtasks: list[SubtaskOut], depends_on: list[DepOut{id,title,state}],
    placements: list[PlacementBrief], next_block: PlacementBrief | None,
    created_by, created_auto_approved, updated_by, updated_auto_approved,
    is_ai: bool,        # created_by or updated_by starts with "agent:" (AGT-7)
    is_auto: bool,      # any auto_approved flag true
    source, created_at, updated_at
```
**Service rules:**
1. Vocab keys must exist & be enabled → else 422 `UNKNOWN_VOCAB`.
2. Calendar inference: if `calendar_id` missing and subject meta has `default_calendar_id` →
   set it, `calendar_inferred=True`. **Never** fall back to any other calendar (SET-3).
3. Subtasks: if present, `sum(weight_min of non-dropped) == est_min`; if `est_min` omitted,
   set it to the sum. Mismatch → 422 `SUBTASK_WEIGHTS_MISMATCH`.
4. Dependencies: all ids exist; no cycles (DFS) → 422 `DEPENDENCY_CYCLE`.
5. `gates` computed: `missing_estimate`, `missing_priority`, `missing_calendar`,
   `dependency_incomplete`, `deferred`.
6. State machine (TSK-3): allowed transitions
   `inbox→scheduled|backlog|done|skipped`, `scheduled→in_progress|partial|done|skipped|inbox|backlog`,
   `in_progress→partial|done|skipped|scheduled`, `partial→in_progress|done|skipped|scheduled`,
   `backlog→inbox`, `done→scheduled (reopen)`, `skipped→inbox`. Only the planning service moves
   `inbox→scheduled` (when a placement is applied) and `scheduled→inbox` (when all placements are removed).
7. `GET /api/tasks` filters: `state` (multi), `flagged=bool`, `subject`, `q` (ILIKE title),
   `created_by=me|agent|any`, `agent_name`, `auto_approved=bool`, `deadline_before`,
   `sort=deadline|created|priority`. Default excludes archived and done older than 7 days.
   Response includes `counts` by tab: `all, inbox, scheduled, overdue, backlog, done, by_agent, auto_approved`.
8. `DELETE` = soft (`archived_at`), user only; removes its future placements in the next plan
   (delete reason `PRECLEAN_SOURCE_CLOSED`). Returns undo token.
9. Every create/edit writes `activity` and enqueues replan.
**Tests:** inference sets `calendar_inferred`; no-calendar task returns gate; agent edit marks
`is_ai`; cycle rejected; filters & counts; delete is soft and undoable.

### BE-08 — Dependencies & subtasks endpoints polish
**Depends on:** BE-07 **Size:** S
Subtasks are edited through `PATCH /api/tasks/{id}` with the full `subtasks` list (replace
semantics; keep ids of retained rows). Toggling a single subtask: `POST /api/tasks/{id}/subtasks/{sid}/toggle`
(returns undo). TSK-8: ticking a subtask reduces remaining by its weight.
**Tests:** proportional remaining; toggle undo.

### BE-09 — Progress, defer, state actions
**Depends on:** BE-07, BE-06 **Size:** M
**Spec:** TSK-4, TSK-6, HAB-8b, UX-1 (+15m)
**Files:** `services/tasks.py`, routes
**Endpoints:**
- `POST /api/tasks/{id}/progress {minutes: int} | {done: true} | {subtask_ids: [...]}`
  → adds to `logged_min` (or ticks subtasks); sets state `in_progress` (if a block is running)
  or `partial` (if remaining > 0 and no block running) or `done` (remaining == 0 or done=true,
  `completed_at=now`). Returns task + undo.
- `POST /api/tasks/{id}/defer {until: date, move_deadline: bool=false, replan_now: bool=false}` → `deferred_until`;
  with `replan_now=true` (used from the calendar review, D-28) the planner runs synchronously and
  the response includes `plan_run_id` so the UI swaps ghosts without waiting for the debounce;
  if `move_deadline`, shift deadline by the same number of days. Activity "deferred". **No
  penalty, no streak** (HAB-8b). Undo.
- `POST /api/tasks/{id}/state {state: done|skipped|backlog|inbox}` with transition validation. Undo.
**Tests:** TSK-4 example: est 90, log 45 → remaining 45 and next plan re-chunks ≥ 30; defer
leaves deadline unless asked; done task's future blocks become safe deletes in the next diff.

### BE-10 — Habits CRUD
**Depends on:** BE-05, BE-02 **Size:** M
**Spec:** HAB-1, HAB-2, HAB-11, SET-9, AGT-3
**DTOs:** `HabitIn {name, weekdays[1..7], ideal_min, min_min?, not_before?, not_after?, ideal_time?, priority_key?, compressible?, calendar_id?}` (defaults from `habit_defaults`);
`HabitOut` adds `state, streak_current, streak_best, consecutive_skips, skip_warning
("one more ends it" when consecutive_skips == threshold−1), compressions_this_week, today:
{occurrence_state, planned_min, actual_min, block}, ended_at, archived_at, is_hard (min==ideal)`.
**Rules:** `compressible` forced false when `min_min == ideal_min`. `DELETE` → HAB-11: set
`state='archived'`, `archived_at=now`, future occurrences deleted (rows with state scheduled and
date ≥ today removed), past occurrences kept, **nothing marked missed**; requires query param
`?confirm=true` (UX-3 hard confirm) else 409 `CONFIRM_REQUIRED` with the consequence text.
`GET /api/habits?include=ended,archived` groups by state.
**Tests:** hard habit compressible forced false; delete without confirm → 409; delete keeps history.

### BE-11 — Habit log, skip, skip-until, streaks, reactivate
**Depends on:** BE-10, BE-06, EN-14 **Size:** L
**Spec:** HAB-5..10, HAB-12, A6, A7, D-17
**Files:** `services/habits.py`, `services/streaks.py`
**Streak engine (`streaks.py`) — single source of truth:**
```
on_done(habit, occ):       occ.state='done'; habit.consecutive_skips = 0
                           habit.streak_current += 1; habit.streak_best = max(best, current)
on_skip(habit, occ):       occ.state='skipped'; habit.consecutive_skips += 1
                           if consecutive_skips >= threshold:
                               habit.streak_current = 0; habit.state='ended'; habit.ended_at=now
on_missed(habit, occ):     occ.state='missed'; habit.streak_current = 0          (D-17)
recompute(habit):          replay all occurrences in date order with the rules above
                           (reactivation boundary: replay starts at active_from)
```
**Endpoints:**
- `POST /api/habits/{id}/log {minutes?: int, done?: bool, date?: date=today}` → tick (done)
  or add minutes; done when `actual_min ≥ min_min` or `done=true`. Undo.
- `POST /api/habits/{id}/skip {scope: "today"|"until", until?: date}` → for `today`: skip
  today's occurrence. For `until`: create/mark every due occurrence date in `[today, until]` as
  skipped with one `skip_batch_id`, applying `on_skip` **in order** (the streak can end inside
  the span — A7; once ended, stop marking further dates). Response includes `released: [{start,
  end}]` and `consequence` text from what-if (HAB-12), plus undo (inverse = restore previous
  occurrence states and streak fields snapshot).
- `GET /api/habits/{id}/skip-preview?until=YYYY-MM-DD` → `{occurrences_in_span, will_end_streak:
  bool, ends_on: date|null, streak_now, message}` — message e.g. *"3 occurrences fall in this
  span — this will end your 14-day streak on Thu 26."* (HAB-8a). For `until` omitted → today only,
  plus what-if `frees` text.
- `POST /api/habits/{id}/reactivate {from: "today"|"tomorrow"}` → state active, streak 0,
  consecutive_skips 0, `active_from` = date, `ended_at` kept in activity. History untouched (HAB-10).
**Tests:** A6 (weekly habit, 3 skips weeks apart → ended, history intact); A7 (daily habit,
skip until next week → third occurrence ends the streak, remaining dates not marked);
log resets skip counter; preview message exact text; undo of skip-until restores streak.

### BE-12 — Prayers service
**Depends on:** BE-05, IN-07 **Size:** M
**Spec:** PRY-1..8, SET-6
**Files:** `services/prayers.py`, `api/routers/prayers.py`
**Steps:**
1. `ensure_instances(session, dates)`: for each date in window and each enabled prayer config
   (Jummah instead of Dhuhr on Fridays if configured), upsert `prayer_instance` with
   anchor/window computed (`fixed_time` or library time + offset; window = anchor + offsets).
   Do not overwrite `state` for `prayed` rows. Store `computed_at`, `drift_min`, `drift_flag`
   from IN-07 for computed prayers (and for fixed prayers whose library time is known, informational).
2. `GET /api/prayers?date=` → list with `{name, label, anchor, window, block{start,end}, state,
   qada_index, drift, next: bool, countdown_min}` and `rule` text; `week` variant returns 7 days compact.
3. `POST /api/prayers/{id}/prayed {at?: datetime=now}` → state prayed, `prayed_at`. **PRY-6
   release is done here, not by the engine:** if the prayer's active placement ends after
   `ceil_to_grid(prayed_at)`, shorten it to `[start, max(start + g, ceil_to_grid(prayed_at))]`; if
   `prayed_at ≤ start`, remove it. Write the change to Google immediately through
   `calendar_writer` (a direct consequence of the user's action, like BE-15 drag), then enqueue
   replan trigger `prayed` so flagged tasks refill the freed time first. Undo restores the block.
4. `POST /api/prayers/{id}/move {start}` (qada moved earlier and prayed, PRY-5) → pin the
   placement at the new time (written to Google via `calendar_writer`) and mark prayed.
   This and step 3 are permitted Google writers (AGENTS.md rule 7).
**Tests:** Friday has jummah not dhuhr; prayed qada releases capacity in the next plan.

### BE-13 — Snapshot builder & plan run service
**Depends on:** EN-15, BE-07, BE-10, BE-12 **Size:** L
**Spec:** ENG-2, ENG-4, ENG-5, RPL-1, RPL-2, FR-7.3
**Files:** `services/snapshot.py`, `services/planning.py`, `api/routers/plan.py`
**Steps:**
1. `snapshot.build(session, now) -> PlanInput`: settings projection; day overrides; obstacle
   external events (02-data-model §2.3 rule) in window; `prayers.ensure_instances` then
   PrayerDay list; fixed = pinned active placements + frozen (active engine placements with
   `start_at < now`); habits (active) with occurrences in window; tasks (non-archived) with
   remaining, ranks, deps; hints = active engine non-pinned future placements; current =
   same list as `CurrentBlock`.
2. `planning.run(session, trigger, actor) -> PlanRunOut`:
   - `pg_advisory_xact_lock(hashtext('plan'))` for the whole run.
   - Insert `plan_run(status='running')`; build snapshot; `input_hash`; `engine.plan`; `engine.diff`.
   - Mark any existing `proposed` run `superseded`.
   - **Calendar gate:** a change whose block has no resolvable calendar (prayers/qada →
     `calendars.prayers_calendar_id`/`qada_calendar_id`; habits → `habit.calendar_id` or
     `calendars.habits_calendar_id`; tasks → `task.calendar_id`), or whose calendar is disabled or
     not writable, is **removed from the changes** and replaced by a flag `CALENDAR_UNROUTED`
     ("Prayers have no calendar — choose one in Settings → Calendars"). The block still occupied
     time inside the engine, so nothing else lands on it.
   - **Suppression (anti-nag):** drop changes whose id is in `suppressed_change` (unexpired).
   - If no changes and no new flags → status `empty`.
   - Else status `proposed`, store changes/flags/summary.
   - **Flag columns** per task: new code (was NULL or different code) → set `flag_code`,
     `flag_reason`, `flag_short_min`, `flag_raised_at = now`, `flag_reminded_on = NULL`; same
     code → update reason/short only (keeps `flag_raised_at`, so OVL-3 reminds once); no flag
     anymore → set all flag columns NULL.
   - **Engine log persistence:** at proposal time persist only **new** flags (as above) and
     `PRAYER_DRIFT`. All other `LogEntry`s are persisted by BE-14 when the change they describe is
     applied (categories shrink, held, release, prayer, placement). `held` entries not tied to a
     change (e.g. `HABIT_HARD_NOT_COMPRESSED`, `PINNED_LEFT_ALONE`) are persisted once per
     (rule, subject, local date) — dedupe with a lookup before insert.
   - Auto-apply is **not** done here; BE-14 adds it as a post-run hook.
   - If `ask` changes exist → enqueue `push` job `plan_approval` (dedupe per ask-set hash, WK-04).
3. Endpoints: `POST /api/plan/run {}` (manual), `GET /api/plan/current` (proposed run or 204),
   `GET /api/plan/diff` (= current or run now), `POST /api/plan/reject {plan_run_id, change_ids?}` →
   all (or the given) changes are inserted into `suppressed_change` (24 h); if all → status
   rejected, `GET /api/plan/runs?limit=`. `POST /api/plan/run {drop_hints: bool=false}` —
   `drop_hints=true` is Settings → "Recompute the whole calendar" (SET-14, confirm in UI).
   Unticked changes in a partial apply are **not** suppressed (they stay proposed, BE-14).
**PlanRunOut:** `{id, status, trigger, started_at, changes[Change], flags[FlagOut], summary:
{create, move, resize, delete, safe, ask, flags}, auto_applied_count}`.
**Tests:** two concurrent runs serialize; unchanged inputs → `empty` (ENG-4); proposed run
superseded; rejected change not re-proposed within 24 h while inputs unchanged; unrouted prayer
calendar → `CALENDAR_UNROUTED` flag and no prayer changes; flag columns new vs same code.

### BE-14 — Apply plan (transactional with Google)
**Depends on:** BE-13, IN-06 **Size:** L
**Spec:** RPL-4, RPL-5, CAL-1, CAL-4, UX-3, AGT-4
**Files:** `services/apply.py`, route in `routers/plan.py`
**Request:** `POST /api/plan/apply {plan_run_id, accept: [change_id], overrides?: {change_id: {start, end}}, confirm: true}` —
`overrides` (D-28): the user dragged a ghost to another slot before accepting. The change is
applied at the override time and the placement is created **pinned** (`owner='user'`). Pre-check:
the override must not overlap a meeting, prayer or qada and must be on the grid (422
`OVERRIDE_INVALID`). Changes whose `requires` pointed at the original target are re-validated.
`confirm` is the UX-3 hard confirm —
`confirm` is the UX-3 hard confirm (the UI shows the dialog; API requires the flag for users;
auto-apply passes it internally).
**Algorithm:**
1. Lock; run must be `proposed` and match id (else 409 `PLAN_STALE` — UI re-fetches).
2. Validate `accept` ⊆ changes and closed under `requires` (409 `CONFLICT_REQUIRES` listing missing ids).
2b. Every accepted change must have a resolved, writable calendar (BE-13 gate) — defensive re-check.
3. Agent without `plan.apply` in `auto_approve` → create `agent_proposal(kind='plan_apply')`
   instead and return 202 `{held: true, proposal_id}` (mockup "HELD").
4. Order operations: deletes → resizes/moves → creates.
5. For each op call the calendar writer (IN-06) — retry once on failure (RPL-5). Keep a journal
   of completed ops `[{op, event_id, before}]`.
6. On second failure: roll back journal in reverse (delete created events, restore moved/resized
   to `before`, re-create deleted with the old payload), mark run `failed` with error, log
   `engine_log(rule='APPLY_ROLLED_BACK', category='apply')`, enqueue alert. **DB untouched.**
7. On success, in **one DB transaction**: upsert placements (status, times, event ids,
   fingerprints, attribution), update `habit_occurrence.planned_min/compressed_min`,
   `prayer_instance.state/qada_index`, task states (`inbox→scheduled` when it gets its first
   placement; `scheduled→inbox` if it lost all), append to `accepted_change_ids`, set
   `decided_by`/`auto_applied`, write `engine_log` per applied change (rule, title, detail,
   effect, actor, auto_approved) and `activity` per affected entity.
8. **Partial apply keeps the run alive:** remove the applied changes from `plan_run.changes`. If
   changes remain, the run stays `proposed` (so `GET /api/plan/current` still shows the leftovers
   and their ids stay valid — `requires` closure guarantees they don't depend on applied ones);
   if none remain, status `applied`, `applied_at = now`.
9. Enqueue `notion_mirror` (NOT-2).
10. **Auto-apply hook** (RPL-4): `planning.run` calls `apply.auto_apply(run)` after storing a
   `proposed` run when `auto_apply_safe` is on: accept = safe changes whose `requires` closure is
   also all-safe; actor `engine`, `auto_approved=True`, no confirm needed. Leftover ask changes
   remain proposed (step 8) and trigger the `plan_approval` push.
**Tests (with fake calendar):** happy path; chained swap (X into Y's old slot, Y elsewhere) commits
(deferred exclusion constraint); partial apply leaves the run proposed with the rest; auto-apply
applies only safe; failure on 3rd op twice → first two rolled back,
calendar equals pre-state, DB unchanged; agent without auto-approve → 202 held; requires closure enforced.

### BE-15 — Placements: drag/pin/unpin, +15m on current block
**Depends on:** BE-14 **Size:** M
**Spec:** ENG-3, A9, UX-1, AGT-2
**Endpoints:**
- `GET /api/placements/{id}` → `{block: Block, why: [str], rule, history: [activity], actions: [str]}` for `BlockDrawer`.
- `POST /api/placements/{id}/move {start, end?}` → validate no overlap with non-pinned active
  blocks? **No** — a user drag is authoritative: set `owner='user', pinned=true`, write the new
  time to Google **immediately** (this is the user's direct action, not an engine change; it
  does not need plan acceptance), log `PINNED_LEFT_ALONE` activity "you pinned Wed 21:00",
  enqueue replan (the engine will move what the pin now overlaps). Undo (restore old time, unpin).
- `POST /api/placements {task_id | habit_id, start, end}` → user-created block, `owner='user'`,
  `pinned=true`, written to Google immediately (calendar = the task's/habit's routed calendar;
  422 `CALENDAR_UNROUTED` if none). Allowed over meetings (D-15). Refused (422
  `OVERLAPS_PRAYER`) over a prayer or qada.
- **Past blocks = logged work (D-15):** for `move` or create where `end ≤ now`: task → `logged_min
  += minutes` (state → partial/done as in BE-09); habit → occurrence of that date `actual_min +=
  minutes` and done when ≥ min (streak via `streaks.on_done`). Activity text names the overlapped
  meeting if any ("worked during Standup"). Undo reverts both the block and the logged minutes.
  Blocks partly in the past are split at `now`: the past part logs, the future part stays as a
  pinned block.
- `POST /api/placements/{id}/unpin` → `pinned=false, owner='engine'`; replan.
- `POST /api/placements/{id}/progress {minutes: 15|30}` → for task chunks: task progress (BE-09);
  for habits: habit log (BE-11). Returns undo. (Today "+15m · +30m · Done" buttons.)
**Tests:** A9 end-to-end: move → pinned → next plan never moves it.

### BE-16 — Decisions (overload) & day overrides
**Depends on:** BE-13, EN-14 **Size:** M
**Spec:** OVL-1..3, D-21
**Endpoints:**
- `GET /api/decisions` → `{flags: [FlagOut grouped: overload | needs_fields | blocked | prayer],
  import_batches_pending, agent_proposals_pending, counts}` — powers the "Needs a decision" screen and badge.
- `GET /api/decisions/{task_id}/levers` → for each applicable lever, run a what-if and return
  `{lever, label, params, effect_text, clears_flag: bool, cost_text}`:
  - `push_deadline` → params `{new_deadline: deadline + 7d}` ("Push the deadline → Sat 29, deadline moves with it")
  - `skip_habit` → for each habit occurrence in range (max 3, those whose skip clears most) → "Skip Gym Thu → frees 2h 00m total, covers the last 30m"
  - `make_time` → extend latest_block_end by `short_min` (rounded up to grid) on the deadline day (or the day before if that day is fully booked) → "Extend Thu by 30m"
  - `reduce_task` → for each undone subtask, smallest that clears → "drop the notes unit (30m)"
- `POST /api/decisions/{task_id}/lever {lever, params}` → performs the action through the normal
  services (task patch, habit skip, day override, subtask drop) with undo; replan.
- Day overrides CRUD: `GET /api/day-overrides?from=&to=`, `PUT /api/day-overrides/{date}
  {earliest_block?, latest_block_end?, reason}`, `DELETE`.
**Tests:** each lever's what-if result for the A4 fixture; lever applies via the right service.

### BE-17 — Today & Week read models
**Depends on:** BE-13 **Size:** M
**Spec:** UX-1, UX-7, NFR-7
**`GET /api/today`** →
```json
{
 "date": "2026-11-22", "now": "…",
 "stats": {"planned_min": 370, "done_min": 165, "left_min": 205, "slack_min": 65},
 "current_block": {Block…, "progress_min": 55, "actions": ["+15","+30","done"]} | null,
 "next_prayer": {"name": "asr", "start": "…", "countdown_min": 102, "progress_pct": 82},
 "timeline": [Block…],          // all blocks of the day incl. meetings, prayers, qada, habits, tasks, ordered
 "habits_today": [{habit_id, name, state, planned_min, actual_min, streak, warning}],
 "engine_notices": [ {rule, title, detail, ts} ],   // last 24h log entries of categories shrink/held/release
 "up_next": [Block…] (next 3),
 "plan": {"proposed_run_id": "…|null", "ask_count": 3, "safe_count": 1},
 "flags_count": 1
}
```
`Block` = `{id, kind: meeting|prayer|qada|habit|task_chunk|pinned, title, start, end, minutes,
ref_type, ref_id, calendar_color, effort_key, priority_key, state, pinned, compressed_from,
chunk_index, chunk_count, overflow, why: [str], is_ai, is_auto, subtitle}` where `subtitle` is the mockup's second
line ("1h 25m · compressed from 2h", "10m · min protected").
**Proposals overlay (D-28):** both `/api/today` and `/api/week` accept `proposals=true` (the web
client always sends it) and then include `proposals: [ProposalBlock]` from the current
`proposed` run, limited to the date range:
`ProposalBlock = {change_id, kind: create|move|resize|delete, classification, title, ref_type,
ref_id, task_id?, block_kind, calendar_color, from?: {start,end}, to?: {start,end}, rule, reason,
why: [str], requires: [change_id], actions: ["accept","not_now","later_date","drag"]}`
(`later_date` only for task changes; `drag` only for create/move of task chunks and habits).
**`GET /api/week?from=`** → 7 days `{date, label, planned_min, done_min, deadlines: n,
overload: {short_min}|null, blocks: [Block…]}` + `total_planned_min`.
**Perf:** both queries < 300 ms warm (NFR-7): single query per table, no N+1 (use `selectinload`).
**Tests:** fixture day equals expected JSON (snapshot test); query count assertion (≤ 8 queries).

### BE-18 — Engine log & activity APIs
**Depends on:** BE-13 **Size:** S
**Spec:** G4, RPL-6, AGT-7/8
`GET /api/log?category=&rule=&actor=user|agent|engine|any&subject_type=&subject_id=&from=&to=&cursor=`
→ `{items: [{id, ts, rule, category, title, detail, effect, actor, is_ai, auto_approved, undo_token?}], next_cursor, counts_by_category}`.
`GET /api/activity?entity_type=&entity_id=` → task/habit history list.
**Tests:** cursor pagination stable; actor filter.

### BE-19 — Settings write API, export/import, precedence preview, audit
**Depends on:** BE-05, BE-02 **Size:** M
**Spec:** SET-0..16, SET-5, SET-14, SET-15, SET-16
- `GET /api/settings` → all sections + `meta: {section: {version, updated_at, updated_by}}` +
  `json_schema` per section (for client-side validation hints).
- `PATCH /api/settings/{section} {data: partial, version}` → deep-merge, validate with the
  section model, optimistic concurrency (409 `SETTINGS_VERSION_CONFLICT`), audit before/after,
  enqueue replan (trigger `settings`). Fields are saved individually by the UI ("every field
  writes on change"), so the PATCH must accept a single field.
- `POST /api/settings/{section}/reset {confirm: true}` → restore defaults for **that section only** (SET-15). Audit.
- `GET /api/settings/export` → `{version, exported_at, settings: {...}, vocab: [...], calendars_routing_by_name: {...}}`
  (no secrets). `POST /api/settings/import {document, dry_run: true}` → returns a section-by-section
  diff; `dry_run:false` applies (audit each).
- `POST /api/settings/precedence/preview {order}` → `{warnings: ["Moving Prayers below Habits would let a habit hold a prayer's slot and force a Qada…"], changes_this_week: summary, sample_changes: [Change…≤10]}` via what-if. Warning rule (SET-5): any key ranked above `prayers` other than `meetings`.
- `GET /api/audit?area=&cursor=`.
**Tests:** single-field patch; version conflict; reset only one section; export→import round trip
yields no diff; preview warning text.

### BE-20 — Vocabulary API
**Depends on:** BE-19 **Size:** S
**Spec:** SET-17
CRUD under `/api/vocab/{kind}`; `reorder {ids: [...]}`; `DELETE` → 409 `VOCAB_IN_USE` with
counts if referenced, unless `?disable=true` (sets enabled=false). Adding an `effort` adds
`buffers_by_effort[key]=0` in the same transaction. `split_mode` items must carry
`meta.behaviour ∈ {atomic, subtasks, auto}`. Every change audited.
**Tests:** in-use delete blocked; effort add creates buffer entry.

### BE-21 — Agent tokens, scopes, limits, proposals
**Depends on:** BE-02, BE-07 **Size:** L
**Spec:** AGT-1..11, SET-13
**Files:** `auth/agent_tokens.py`, `auth/scopes.py`, `services/agents.py`, `api/routers/agent.py`
**Steps:**
1. Token format `sch_` + 32 urlsafe chars. Store `sha256(token)` and prefix. Plain token shown
   **once** in the create response.
2. Scopes: `read, tasks.create, tasks.edit, blocks.move, plan.apply`. Validation rejects any
   other string (AGT-3: delete/habits/settings cannot even be named).
3. Per-request: look up token (active), check rate limit (`agent_request_log` rows in last hour
   < `rate_limit_per_hour`) and daily cap (sum of `rows` today < `daily_cap`); else 429 with
   `Retry-After`. Log request after handling.
4. **Auto-approve logic** (AGT-4, AGT-11): when an agent calls a mutating endpoint with scope S:
   - S ∈ token.auto_approve → execute now, `auto_approved=True` on every written record (AUTO marker).
   - else → store `agent_proposal` with the exact payload, return 202 `{held: true, proposal_id}`.
   The user approves in-app (`POST /api/agent/proposals/{id}/approve`) → replay the payload
   through the same service with actor `agent:<name>`, `auto_approved=False`.
5. Revoke (AGT-9): status revoked; no change to past records.
6. `GET /api/agent/activity?token_id=&limit=` → last N request-log rows joined with outcomes
   (`AUTO` / `HELD` badges in mockup web/09).
7. Token edit: scopes, auto_approve, limits, name (name change does not rewrite history; the
   actor string of old records keeps the old name).
**Tests:** forbidden scope names rejected; 429 after limit; held proposal approve → task created
with `is_ai` and not auto; revoked token → 401; agent cannot call DELETE task (403).

### BE-22 — NL capture & bulk import (review flow)
**Depends on:** BE-07, IN-12 **Size:** L
**Spec:** CAP-1..8, UX-5, UX-10, AGT-5, AGT-11, D-19
**Files:** `services/capture/parser.py` (deterministic), `services/capture/llm_parse.py`,
`services/capture/bulk.py`, `api/routers/capture.py`
**Deterministic parser** (`parse_line(text, settings, today) -> DraftRow`):
- Duration: `(\d+(\.\d+)?)\s*(h|hr|hrs|hour|hours)`, `(\d+)\s*(m|min|mins|minutes)`, `1h 45`,
  `1h45m`, `90m`, `1.5h` → `est_min` (rounded to grid). Unrecognised unit → note
  `parsed "1h 45" as unknown unit` and leave est empty (mockup web/08).
- Priority words from `task_defaults.inference.priority_words` (default `{"high": ["high","urgent","p1","!!"], "medium": ["med","medium","p2"], "low": ["low","p3"]}`).
- Deadline: `before|by|due (mon|tue|…|friday|tomorrow|today|next week|<date>)` → that day at
  23:59 local; weekday means the **next** occurrence (today counts if later than now and the
  phrase is "by today"). Phrases are configurable (`inference.deadline_phrases`).
- Subject: first vocab subject whose `meta.keywords` matches (case-insensitive word boundary); else `task_defaults.subject_key`.
- Calendar: subject's default calendar (inferred=True) else null.
- Effort: subject `meta.default_effort` else default.
- Estimate inference (UX-5): if no duration and a previous task with the same normalised title
  prefix (text before ` — ` or `:`) exists, use its `est_min` and mark `est_source='last_similar'`.
- Dependencies in bulk: `after <title-prefix>` or `depends on <ref>` → link to a row in the same batch or an existing task by prefix match.
- Bulk splitting: split pasted text by lines; support `|`-separated columns
  (`W2D1 — Auth bypass | 2h | High | due Mon`), markdown bullets, numbered lists.
**DraftRow:** `{row: int, title, est_min, est_source, priority_key, deadline, subject_key,
calendar_id, calendar_inferred, effort_key, split_key, depends_on_rows: [int],
depends_on_task_ids: [UUID], notes, issues: ["missing_estimate", "no_calendar", "unknown_unit"],
include: bool}`.
**LLM path:** only for `POST /api/capture/parse {text, use_llm: true}` when `llm.enabled`.
Prompt the model to return JSON rows with the same fields (keys only from vocab lists provided in
the prompt); validate with Pydantic; anything invalid is dropped to null (never guessed). Merge:
LLM fills only fields the deterministic parser left empty. Timeout → fall back silently, response
`llm_used=false, llm_error`.
**Endpoints:**
- `POST /api/capture/parse {text, use_llm?}` → `{draft: DraftRow}` for a single line (CAP-1 chips). Nothing stored.
- `POST /api/tasks/bulk {mode: "parse", text, source}` → creates `import_batch(status='draft')`,
  returns `{batch_id, rows, stats: {parsed, complete, missing_est, no_calendar, will_schedule,
  will_flag, dependencies}}` (mockup web/08 header).
- `PATCH /api/import-batches/{id}/rows/{row}` → edit a row (same validation as TaskIn).
- `POST /api/import-batches/{id}/commit {rows?: [int], then_plan: bool}` → create tasks for
  included rows; rows missing est/priority/calendar are created in `inbox` with gates (UX-10
  "needs a decision"). Response per row `{row, status: created|rejected, task_id?, reason?}`
  (AGT-5). Partial failures don't roll back successes. If `then_plan`, run the planner and return
  the plan run id ("Commit & preview plan →").
- `POST /api/tasks/bulk {mode: "commit", rows: [DraftRow...]}` — agent one-shot path (no batch):
  honours `batch_max` (422 `BATCH_TOO_LARGE`); with `tasks.create` auto-approved → creates
  directly (AGT-11); otherwise → `agent_proposal(kind='bulk_create')` + an `import_batch` so the
  user reviews it in the same review table (CAP-4 parity).
**Tests:** parser table (≥ 25 cases incl. "2h DBMS revision before friday, high"); bulk parse of
the mockup's 4-line sample; commit with a mix of complete and incomplete rows; agent bulk with
and without auto-approve.

### BE-23 — Insights
**Depends on:** BE-14, BE-11 **Size:** M
**Spec:** INS-1..5
`GET /api/insights?range=week|month&from=` →
```json
{
 "adherence": {"pct": 78, "done_min": 760, "planned_min": 970,
               "by_day": [{"date","planned_min","done_min"}]},        // INS-1
 "habits": {"kept_pct": 87, "kept": 20, "total": 23,
            "per_habit": [{"habit_id","name","days":[{"date","state":"full|compressed|skipped|missed|none|ended"}]}]}, // INS-2
 "subjects": [{"subject_key","label","minutes","pct"}],              // INS-3
 "debt": {"backlog_count": 14, "no_est_or_deadline": 14, "overdue_trend": [{"date","count"}]},  // INS-4
 "compressions": {"total": 9, "per_habit": [{"habit_id","name","week","count"}]}               // INS-5
}
```
Planned = sum of applied placement minutes for tasks+habits in range; done = task `logged_min`
deltas (from activity `progress`) + habit `actual_min`. Ended-habit gaps render as `ended` days (HAB-10 "shows a gap").
**Tests:** fixture week → exact numbers.

### BE-24 — Recurring tasks
**Depends on:** BE-07, WK-02 **Size:** M
**Spec:** TSK-9, D-20
`RecurrenceIn {freq: daily|weekly, interval: int=1, weekdays?: [1..7], until?: date, count?: int,
deadline_time?: time="23:59"}`. A task with `recurrence` is a **template** (state `backlog`,
never scheduled itself). Worker job `materialize_recurrences` (hourly and on template change)
creates instance tasks for occurrence dates within the window that don't exist yet
(`UNIQUE(series_id, series_date)`), copying fields; deadline = date + deadline_time. Editing the
template affects only future, not-yet-materialised instances (and optionally unstarted ones: flag `apply_to_future=true`).
**Tests:** weekly Mon/Thu within 14 days → 4 instances; idempotent re-run.

### BE-25 — Onboarding support
**Depends on:** IN-03, BE-10 **Size:** S
**Spec:** wireframe 05 (first run), WEB-27
- `GET /api/onboarding/state` → `{steps: {google, location, office_hours, calendars_habits}, done: bool}`
  from `settings.general.onboarded_steps`; `POST /api/onboarding/step {step, done}`.
- `GET /api/onboarding/habit-suggestions` → scan the next 14 days of **recurring** events
  (`recurringEventId` present) in writable/meeting calendars via the calendar port; group by
  series; propose `{name, weekdays, ideal_min (median duration), min_min (= habit_defaults.min_min
  capped at ideal), not_before/not_after (earliest start − 30m / latest end + 30m), ideal_time
  (mode start)}`. Read-only — nothing is created until the user accepts each suggestion (normal
  `POST /api/habits`).
**Tests:** fake calendar with a Mon–Sat "Gym 06:00–09:00" series → one suggestion with weekdays 1–6.

### BE-26 — Test-only seed endpoint
**Depends on:** BE-13 **Size:** S
Router mounted only when `APP_ENV == "test"`: `POST /api/__test/seed/{scenario}` (wipes and loads
a named scenario from `backend/tests/fixtures/scenarios/*.py`), `POST /api/__test/clock {now}` (sets
`clock.set_fixed`). Used by Playwright (11-testing.md). A test asserts the router is absent when
`APP_ENV=prod`.

### BE-27 — Instant re-plan & live version (D-29)
**Depends on:** WK-01, BE-13, BE-14 **Size:** S
**Files:** migration (data_version table + triggers), `api/routers/version.py`, `services/jobs.py`
1. Migration: `data_version` row (id 1) + `bump_data_version()` statement triggers (02-data-model §2.9).
2. `GET /api/version` → `{data_version, plan_run_id: uuid|null, ask_count, safe_applied_last_min,
   last_plan_at, worker_ok: bool}`. Single cheap query; target < 20 ms.
3. `enqueue_replan` merges `released` intervals on conflict:
   `payload = jsonb_set(job.payload, '{released}', (job.payload->'released') || (EXCLUDED.payload->'released'))`.
4. Audit every mutating service for the replan call (a test parametrised over all mutating routes
   asserts that a `replan` job is queued, D-29).
**Tests:** a task edit bumps the version; burst of 5 edits within 2 s → one replan job; with the
worker running in-process (test mode), an edit reaches the fake Google calendar in < 10 s.
