# 02 — Data Model, Settings Schema & Seed Data

This extends requirements §19. **Postgres is the source of truth** (NOT-1). All tables live in
schema `public`. All `id` columns are `uuid DEFAULT uuidv7()` unless stated. Every
table has `created_at timestamptz NOT NULL DEFAULT now()`. Mutable tables also have
`updated_at timestamptz NOT NULL DEFAULT now()`, set by the ORM on update.

Enum-like columns are `text` + `CHECK (col IN (...))`. The allowed values are listed inline.

IDs use PostgreSQL's built-in **`uuidv7()`** (PG 18+): time-ordered, so inserts stay index-friendly
and IDs sort by creation time. Extensions required (migration 0001): `btree_gist` (no-overlap
exclusion constraint).

---

## 1. Attribution columns (AGT-6) — reused pattern

Any table marked **[attr]** has:

```
created_by            text    NOT NULL   -- 'user' | 'agent:<name>' | 'engine' | 'system'
created_auto_approved boolean NOT NULL DEFAULT false
updated_by            text    NOT NULL
updated_auto_approved boolean NOT NULL DEFAULT false
```

Implement as a SQLAlchemy mixin `AttributionMixin` in `models/base.py`.

---

## 2. Tables

### 2.1 Settings & vocabularies

```sql
CREATE TABLE app_setting (
  section     text PRIMARY KEY,           -- see §3 for the list of sections
  data        jsonb NOT NULL,             -- validated by the section's Pydantic model
  version     integer NOT NULL DEFAULT 1, -- optimistic concurrency, bump on every write
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  text NOT NULL
);

CREATE TABLE vocab_item (                 -- SET-17
  id        uuid PRIMARY KEY DEFAULT uuidv7(),
  kind      text NOT NULL CHECK (kind IN ('subject','priority','effort','split_mode')),
  key       text NOT NULL,                -- stable machine key, never changes after create
  label     text NOT NULL,                -- user-visible, renamable
  sort      integer NOT NULL,
  enabled   boolean NOT NULL DEFAULT true,
  meta      jsonb NOT NULL DEFAULT '{}',  -- per-kind payload, see §4
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kind, key)
);
```

Removing a vocab item that is referenced → soft: set `enabled=false` (it disappears from forms,
existing rows keep their key and render the label with a "disabled" style). Hard delete only
when unreferenced.

### 2.2 Users, auth, agents

```sql
CREATE TABLE user_account (               -- exactly one row
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  email        text NOT NULL UNIQUE,
  display_name text NOT NULL DEFAULT 'Me',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE passkey_credential (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  credential_id  bytea NOT NULL UNIQUE,
  public_key     bytea NOT NULL,
  sign_count     bigint NOT NULL DEFAULT 0,
  transports     text[] NOT NULL DEFAULT '{}',
  name           text NOT NULL,             -- "MacBook Touch ID"
  created_at     timestamptz NOT NULL DEFAULT now(),
  last_used_at   timestamptz
);

CREATE TABLE auth_session (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  token_hash    bytea NOT NULL UNIQUE,      -- HMAC-SHA256(APP_SESSION_SECRET, raw token)
  user_agent    text,
  ip            inet,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL,       -- sliding 30 days
  revoked_at    timestamptz
);

CREATE TABLE magic_link (
  token_hash  bytea PRIMARY KEY,
  expires_at  timestamptz NOT NULL,         -- 15 minutes
  used_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_token (                  -- AGT-2..10
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  name                text NOT NULL UNIQUE,  -- e.g. 'assistant-bot'; actor = 'agent:'||name
  token_prefix        text NOT NULL,         -- first 8 chars shown in UI: 'sch_ab12'
  token_hash          bytea NOT NULL UNIQUE,
  scopes              text[] NOT NULL,       -- subset of: read, tasks.create, tasks.edit, blocks.move, plan.apply
  auto_approve        text[] NOT NULL DEFAULT '{}', -- subset of scopes (never 'read')
  rate_limit_per_hour integer NOT NULL,
  daily_cap           integer NOT NULL,
  batch_max           integer NOT NULL,
  status              text NOT NULL CHECK (status IN ('active','revoked')) DEFAULT 'active',
  created_at          timestamptz NOT NULL DEFAULT now(),
  last_used_at        timestamptz,
  revoked_at          timestamptz,
  CHECK (auto_approve <@ scopes)
);

CREATE TABLE agent_request_log (           -- rate limiting + activity feed
  id          bigserial PRIMARY KEY,
  token_id    uuid NOT NULL REFERENCES agent_token(id),
  ts          timestamptz NOT NULL DEFAULT now(),
  method      text NOT NULL,
  path        text NOT NULL,
  status      integer NOT NULL,
  rows        integer NOT NULL DEFAULT 1    -- batch size counts toward the daily cap
);
CREATE INDEX ON agent_request_log (token_id, ts);

CREATE TABLE agent_proposal (              -- agent action held for approval (AGT-4)
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  token_id    uuid NOT NULL REFERENCES agent_token(id),
  scope       text NOT NULL,                -- which scope required approval
  kind        text NOT NULL CHECK (kind IN ('task_create','task_edit','block_move','plan_apply','bulk_create')),
  payload     jsonb NOT NULL,               -- the exact request body to replay on approval
  summary     text NOT NULL,                -- "Create 18 tasks — cybersec week 2"
  status      text NOT NULL CHECK (status IN ('pending','approved','rejected','expired')) DEFAULT 'pending',
  result      jsonb,
  created_at  timestamptz NOT NULL DEFAULT now(),
  decided_at  timestamptz
);
```

### 2.3 Google & calendars

```sql
CREATE TABLE google_account (               -- at most one row (id fixed = 1)
  id                 integer PRIMARY KEY CHECK (id = 1),
  email              text NOT NULL,
  scopes             text[] NOT NULL,
  refresh_token_enc  bytea NOT NULL,         -- Fernet
  access_token_enc   bytea,
  access_expires_at  timestamptz,
  status             text NOT NULL CHECK (status IN ('connected','expired','revoked','error')),
  last_error         text,
  connected_at       timestamptz NOT NULL DEFAULT now(),
  last_ok_at         timestamptz
);

CREATE TABLE oauth_state (                  -- CSRF state for the OAuth dance
  state       text PRIMARY KEY,
  code_verifier text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()   -- valid 10 minutes
);

CREATE TABLE calendar (                     -- SET-2
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  google_calendar_id  text NOT NULL UNIQUE,
  summary             text NOT NULL,        -- Google name, refreshed on discovery
  label               text,                 -- optional local rename
  color               text NOT NULL,        -- hex from Google
  access_role         text NOT NULL,        -- owner | writer | reader | freeBusyReader
  read_meetings       boolean NOT NULL DEFAULT false, -- feed meetings (OFF-2)
  writable            boolean NOT NULL DEFAULT false, -- app may write blocks here
  treat_as_busy       boolean NOT NULL DEFAULT true,  -- events are obstacles
  enabled             boolean NOT NULL DEFAULT true,
  sync_token          text,                 -- incremental sync (IN-05)
  last_synced_at      timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT writable OR access_role IN ('owner','writer'))
);

CREATE TABLE external_event (               -- meetings & other busy events (read-only)
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  calendar_id      uuid NOT NULL REFERENCES calendar(id) ON DELETE CASCADE,
  google_event_id  text NOT NULL,
  summary          text NOT NULL DEFAULT '',
  start_at         timestamptz NOT NULL,
  end_at           timestamptz NOT NULL,
  all_day          boolean NOT NULL DEFAULT false,
  transparency     text NOT NULL DEFAULT 'opaque',   -- opaque | transparent
  response_status  text,                              -- self attendee: accepted | declined | tentative | needsAction
  cancelled        boolean NOT NULL DEFAULT false,
  etag             text,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (calendar_id, google_event_id)
);
CREATE INDEX ON external_event (start_at, end_at);
```

An external event is an **obstacle** iff: calendar.enabled AND calendar.read_meetings AND
calendar.treat_as_busy AND NOT cancelled AND transparency='opaque' AND response_status IS
DISTINCT FROM 'declined' AND (NOT all_day OR settings.calendars.all_day_events_busy).
Events written by the app itself (detected by extended property, IN-05) are **never** stored
here.

### 2.4 Tasks

```sql
CREATE TABLE task (                         -- [attr]
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  title            text NOT NULL CHECK (length(title) BETWEEN 1 AND 300),
  notes            text NOT NULL DEFAULT '',
  est_min          integer CHECK (est_min > 0),             -- NULL = missing (gate)
  priority_key     text,                                    -- vocab priority; NULL = missing (gate)
  deadline         timestamptz,                             -- NULL = no deadline
  effort_key       text,                                    -- vocab effort; NULL treated as settings.task_defaults.effort_key
  split_key        text NOT NULL,                           -- vocab split_mode key
  subject_key      text,                                    -- vocab subject
  calendar_id      uuid REFERENCES calendar(id),            -- NULL = missing (gate, SET-3)
  calendar_inferred boolean NOT NULL DEFAULT false,         -- shows the "auto" tag in review
  min_chunk_min    integer CHECK (min_chunk_min >= 5),      -- NULL = use block_rules.min_chunk_min
  state            text NOT NULL CHECK (state IN ('inbox','scheduled','in_progress','partial','done','skipped','backlog')) DEFAULT 'inbox',
  logged_min       integer NOT NULL DEFAULT 0 CHECK (logged_min >= 0),
  deferred_until   date,                                    -- TSK-6: not placed before this local date
  flag_code        text,                                    -- rule code; NULL = not flagged (D-08)
  flag_reason      text,                                    -- human sentence
  flag_short_min   integer,                                 -- minutes that could not be placed
  flag_raised_at   timestamptz,
  flag_reminded_on date,                                    -- OVL-3: one reminder, the morning after
  source           text NOT NULL CHECK (source IN ('manual','nl','bulk','agent','recurrence')) DEFAULT 'manual',
  import_batch_id  uuid REFERENCES import_batch(id),
  recurrence       jsonb,                                   -- D-20, only on series templates
  series_id        uuid REFERENCES task(id),                -- instance → template
  series_date      date,                                    -- instance's occurrence date
  completed_at     timestamptz,
  archived_at      timestamptz,                             -- soft delete
  -- attribution
  created_by text NOT NULL, created_auto_approved boolean NOT NULL DEFAULT false,
  updated_by text NOT NULL, updated_auto_approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (series_id, series_date)
);
CREATE INDEX ON task (state) WHERE archived_at IS NULL;
CREATE INDEX ON task (deadline) WHERE archived_at IS NULL;
CREATE INDEX ON task (created_by);

CREATE TABLE subtask (
  id         uuid PRIMARY KEY DEFAULT uuidv7(),
  task_id    uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  name       text NOT NULL,
  weight_min integer NOT NULL CHECK (weight_min > 0),
  sort       integer NOT NULL,
  done       boolean NOT NULL DEFAULT false,
  done_at    timestamptz,
  dropped    boolean NOT NULL DEFAULT false   -- OVL-2 "reduce the task"
);
-- Service-level invariant (TSK-8): sum(weight_min WHERE NOT dropped) == task.est_min when any subtasks exist.

CREATE TABLE task_dependency (
  task_id            uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  depends_on_task_id uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, depends_on_task_id),
  CHECK (task_id <> depends_on_task_id)
);
-- Service-level invariant: no cycles (DFS check on insert).

CREATE TABLE import_batch (                 -- CAP-3, UX-10
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  source       text NOT NULL CHECK (source IN ('nl','bulk','agent')),
  raw_text     text NOT NULL,
  rows         jsonb NOT NULL,              -- array of DraftRow (04-backend-api.md §BE-22)
  status       text NOT NULL CHECK (status IN ('draft','committed','discarded')) DEFAULT 'draft',
  created_by   text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  committed_at timestamptz
);
```

**Remaining minutes of a task** (used everywhere, implement once in `services/tasks.py::remaining_min`):
```
if task has non-dropped subtasks:
    remaining = sum(weight_min for subtasks where not done and not dropped)
    # logged_min against the current chunk is spread: remaining -= min(logged_min_unattributed, remaining)
else:
    remaining = max(0, est_min - logged_min)
# TSK-4 / D-25: a remainder left by partial progress is re-chunked to ≥ min chunk:
if 0 < remaining < min_chunk and (logged_min > 0 or any subtask done):
    remaining = min_chunk
```
Keep it simple: when subtasks exist, logging progress either ticks subtasks or adds to
`logged_min`. `logged_min` counts only minutes **not** already covered by a ticked subtask.

### 2.5 Habits

```sql
CREATE TABLE habit (                        -- [attr]
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  name               text NOT NULL,
  weekdays           smallint[] NOT NULL CHECK (array_length(weekdays,1) >= 1), -- ISO 1=Mon … 7=Sun
  ideal_min          integer NOT NULL CHECK (ideal_min > 0),
  min_min            integer NOT NULL CHECK (min_min > 0),
  not_before         time NOT NULL,
  not_after          time NOT NULL,          -- latest END time
  ideal_time         time,                   -- preferred START; NULL = earliest in window
  priority_key       text NOT NULL,
  compressible       boolean NOT NULL,       -- forced false when min_min = ideal_min (HAB-2)
  calendar_id        uuid REFERENCES calendar(id), -- NULL = settings.calendars.habits_calendar_id
  state              text NOT NULL CHECK (state IN ('active','ended','archived')) DEFAULT 'active',
  streak_current     integer NOT NULL DEFAULT 0,
  streak_best        integer NOT NULL DEFAULT 0,
  consecutive_skips  integer NOT NULL DEFAULT 0,
  active_from        date NOT NULL,          -- first date occurrences may exist (reactivate sets this)
  ended_at           timestamptz,
  archived_at        timestamptz,            -- HAB-11 "Ended <date>" after delete
  created_by text NOT NULL, created_auto_approved boolean NOT NULL DEFAULT false,
  updated_by text NOT NULL, updated_auto_approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (min_min <= ideal_min),
  CHECK (not_before < not_after)
);

CREATE TABLE habit_occurrence (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  habit_id       uuid NOT NULL REFERENCES habit(id) ON DELETE CASCADE,
  date           date NOT NULL,              -- local date
  state          text NOT NULL CHECK (state IN ('scheduled','done','skipped','missed')) DEFAULT 'scheduled',
  planned_min    integer,                    -- last applied placement length
  actual_min     integer NOT NULL DEFAULT 0, -- logged
  compressed_min integer NOT NULL DEFAULT 0, -- ideal - planned when shrunk (display only, HAB-5)
  skip_batch_id  uuid,                       -- groups a "skip until" span
  decided_at     timestamptz,
  decided_by     text,
  decided_auto_approved boolean NOT NULL DEFAULT false,
  UNIQUE (habit_id, date)
);
```

Occurrence rows are created lazily: (a) by the planner service for each due date in the window
(`state='scheduled'`), (b) by skip-until for every due date in the span, (c) by the nightly
rollover for yesterday if missing. **Streak fields on `habit` are derived caches**; the function
`services/streaks.py::recompute(habit_id)` must be able to rebuild them from occurrences
(used by restore and tests).

### 2.6 Prayers

Prayer **configuration** lives in settings (§3 `prayers`). Daily instances:

```sql
CREATE TABLE prayer_instance (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  date          date NOT NULL,
  name          text NOT NULL CHECK (name IN ('fajr','dhuhr','jummah','asr','maghrib','isha')),
  anchor_at     timestamptz NOT NULL,     -- preferred start (fixed or computed)
  window_start  timestamptz NOT NULL,
  window_end    timestamptz NOT NULL,
  duration_min  integer NOT NULL,
  computed_at   timestamptz,              -- library value (for computed or cross-checked prayers)
  drift_min     integer,                  -- |computed - cross-check|
  drift_flag    boolean NOT NULL DEFAULT false,
  state         text NOT NULL CHECK (state IN ('normal','shifted','qada','prayed')) DEFAULT 'normal',
  qada_index    integer,                  -- stacking order after Isha (1-based)
  prayed_at     timestamptz,
  prayed_by     text,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (date, name)
);
```

The block itself is a `placement` row with `ref_type='prayer'`, `ref_id = prayer_instance.id`.

### 2.7 Placements (the calendar blocks the app owns)

```sql
CREATE TABLE placement (                    -- [attr]
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  ref_type         text NOT NULL CHECK (ref_type IN ('task','habit','prayer')),
  ref_id           uuid NOT NULL,             -- task.id | habit_occurrence.id | prayer_instance.id
  kind             text NOT NULL CHECK (kind IN ('task_chunk','habit','prayer','qada')),
  local_date       date NOT NULL,             -- local date of start
  start_at         timestamptz NOT NULL,
  end_at           timestamptz NOT NULL,
  calendar_id      uuid NOT NULL REFERENCES calendar(id),
  google_event_id  text,                      -- NULL until applied
  gcal_etag        text,
  fingerprint      text,                      -- sha1(start|end|summary) as last written (CAL-2/3)
  owner            text NOT NULL CHECK (owner IN ('engine','user')) DEFAULT 'engine',
  pinned           boolean NOT NULL DEFAULT false,  -- ENG-3
  status           text NOT NULL CHECK (status IN ('active','removed')) DEFAULT 'active',
  created_plan_run_id uuid REFERENCES plan_run(id),
  updated_plan_run_id uuid REFERENCES plan_run(id),
  meta             jsonb NOT NULL DEFAULT '{}', -- {"why": [...], "chunk_index": 1, "chunk_count": 4, "compressed_from": 180}
  created_by text NOT NULL, created_auto_approved boolean NOT NULL DEFAULT false,
  updated_by text NOT NULL, updated_auto_approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_at > start_at),
  CHECK (owner = 'engine' OR pinned)        -- a user-owned block is always pinned
);
CREATE INDEX ON placement (ref_type, ref_id) WHERE status = 'active';
CREATE INDEX ON placement (local_date) WHERE status = 'active';
CREATE UNIQUE INDEX ON placement (google_event_id) WHERE google_event_id IS NOT NULL;

-- placement.calendar_id is NOT NULL: a block whose calendar is unresolved is never applied (BE-14 step 2b).
-- FR-7.1 No double-booking among non-pinned active blocks (D-15):
ALTER TABLE placement ADD CONSTRAINT placement_no_overlap
  EXCLUDE USING gist (tstzrange(start_at, end_at, '[)') WITH &&)
  WHERE (status = 'active' AND NOT pinned)
  DEFERRABLE INITIALLY DEFERRED;   -- checked at COMMIT, so chained moves/swaps in one apply are fine
```

FR-7.2 (a pending qada is never task-filled) is guaranteed by the same exclusion constraint,
because qada blocks are non-pinned active placements. The engine invariant checker (EN-12)
checks it again before anything is stored.

### 2.8 Planning, history, audit

```sql
CREATE TABLE plan_run (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  trigger        text NOT NULL CHECK (trigger IN ('hourly','task_change','calendar_change','manual','agent','prayed','skip','settings','restore')),
  status         text NOT NULL CHECK (status IN ('running','proposed','applied','rejected','superseded','failed','empty')),
  input_hash     text NOT NULL,          -- sha256 of canonical engine input (idempotence debug)
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz,
  duration_ms    integer,
  changes        jsonb NOT NULL DEFAULT '[]',   -- list[Change] (03-engine.md §9)
  flags          jsonb NOT NULL DEFAULT '[]',   -- list[Flag]
  summary        jsonb NOT NULL DEFAULT '{}',   -- counts per kind/class
  accepted_change_ids text[] NOT NULL DEFAULT '{}',
  auto_applied   boolean NOT NULL DEFAULT false,
  applied_at     timestamptz,
  error          text,
  requested_by   text NOT NULL,
  decided_by     text,
  decided_auto_approved boolean NOT NULL DEFAULT false
);
-- FR-7.3 only one active plan version:
CREATE UNIQUE INDEX plan_run_single_proposed ON plan_run ((true)) WHERE status = 'proposed';
CREATE UNIQUE INDEX plan_run_single_running  ON plan_run ((true)) WHERE status = 'running';

CREATE TABLE calendar_orphan (              -- IN-05: our events with no placement; deleted only via review
  google_event_id text PRIMARY KEY,
  calendar_id     uuid NOT NULL REFERENCES calendar(id) ON DELETE CASCADE,
  start_at        timestamptz NOT NULL,
  end_at          timestamptz NOT NULL,
  summary         text NOT NULL DEFAULT '',
  found_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE suppressed_change (            -- user declined this exact change (anti-nag, BE-13)
  change_id   text PRIMARY KEY,             -- deterministic id from engine diff (§8.3 of 03-engine)
  plan_run_id uuid NOT NULL REFERENCES plan_run(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL          -- created_at + 24h; ids change by themselves when inputs change
);

CREATE TABLE engine_log (                   -- RPL-6, G4; first-class screen
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  plan_run_id   uuid REFERENCES plan_run(id),
  rule          text NOT NULL,              -- rule code
  category      text NOT NULL CHECK (category IN ('shrink','held','prayer','release','placement','flag','pin','sync','apply','system')),
  subject_type  text,                       -- task | habit | prayer | placement | plan
  subject_id    uuid,
  title         text NOT NULL,              -- "Gym gave up 30 minutes — not 45"
  detail        text NOT NULL DEFAULT '',   -- one-line reason
  effect        jsonb NOT NULL DEFAULT '{}',-- {"delta_min": -30, "floor_min": 60, ...}
  actor         text NOT NULL,
  auto_approved boolean NOT NULL DEFAULT false,
  undo_token    text                        -- if undoable
);
CREATE INDEX ON engine_log (ts DESC);
CREATE INDEX ON engine_log (subject_type, subject_id);

CREATE TABLE activity (                     -- per-entity history (task detail "History", AGT-7)
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  entity_type   text NOT NULL,              -- task | habit | prayer | placement | settings | agent_token
  entity_id     uuid,
  kind          text NOT NULL,              -- created | edited | moved | pinned | unpinned | progress | deferred | skipped | done | deleted | reactivated | flagged | unflagged | applied
  summary       text NOT NULL,              -- "you pinned Wed 21:00"
  data          jsonb NOT NULL DEFAULT '{}',-- {"before":…, "after":…}
  actor         text NOT NULL,
  auto_approved boolean NOT NULL DEFAULT false
);
CREATE INDEX ON activity (entity_type, entity_id, ts DESC);

CREATE TABLE audit_entry (                  -- SET-14 (settings & security changes)
  id         bigserial PRIMARY KEY,
  ts         timestamptz NOT NULL DEFAULT now(),
  actor      text NOT NULL,
  area       text NOT NULL,                 -- settings section, 'vocab:<kind>', 'google', 'agent_token', 'auth'
  action     text NOT NULL,                 -- update | reset | create | delete | connect | disconnect | revoke | import
  before     jsonb,
  after      jsonb
);

CREATE TABLE day_override (                 -- D-21 "make time"
  date             date PRIMARY KEY,
  earliest_block   time,
  latest_block_end time,
  reason           text NOT NULL DEFAULT '',
  created_by       text NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);
```

### 2.9 Infra tables

```sql
CREATE TABLE job (                          -- WK-01 queue
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  kind        text NOT NULL,                -- replan | apply_plan | sync_calendars | notion_mirror | push | …
  payload     jsonb NOT NULL DEFAULT '{}',
  dedupe_key  text,                         -- e.g. 'replan' → coalesces bursts
  run_after   timestamptz NOT NULL DEFAULT now(),
  status      text NOT NULL CHECK (status IN ('queued','running','done','failed')) DEFAULT 'queued',
  attempts    integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  last_error  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  started_at  timestamptz,
  finished_at timestamptz
);
CREATE UNIQUE INDEX job_dedupe_queued ON job (dedupe_key) WHERE status = 'queued' AND dedupe_key IS NOT NULL;
CREATE INDEX ON job (status, run_after);

CREATE TABLE scheduled_run (                -- NFR-3 run accounting
  id            bigserial PRIMARY KEY,
  job_name      text NOT NULL,
  scheduled_for timestamptz NOT NULL,
  started_at    timestamptz,
  finished_at   timestamptz,
  status        text NOT NULL CHECK (status IN ('started','ok','failed','missed')),
  error         text
);
CREATE INDEX ON scheduled_run (job_name, scheduled_for DESC);

CREATE TABLE calendar_watch (               -- D-29 Google push channels (IN-15)
  channel_id   text PRIMARY KEY,               -- uuid we generate
  calendar_id  uuid NOT NULL REFERENCES calendar(id) ON DELETE CASCADE,
  resource_id  text NOT NULL,                  -- from Google's watch response
  token_hash   bytea NOT NULL,                 -- HMAC of the channel token we sent
  expires_at   timestamptz NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  stopped_at   timestamptz
);

CREATE TABLE data_version (                  -- D-29 live refresh; exactly one row (id = 1)
  id       integer PRIMARY KEY CHECK (id = 1),
  version  bigint NOT NULL DEFAULT 0,
  bumped_at timestamptz NOT NULL DEFAULT now()
);
-- Statement-level trigger on task, subtask, task_dependency, habit, habit_occurrence,
-- prayer_instance, placement, plan_run, external_event, app_setting, vocab_item, day_override:
--   CREATE FUNCTION bump_data_version() RETURNS trigger LANGUAGE plpgsql AS $$
--   BEGIN UPDATE data_version SET version = version + 1, bumped_at = now() WHERE id = 1; RETURN NULL; END $$;
--   CREATE TRIGGER <t>_bump AFTER INSERT OR UPDATE OR DELETE ON <t> FOR EACH STATEMENT EXECUTE FUNCTION bump_data_version();

CREATE TABLE heartbeat (
  name        text PRIMARY KEY,               -- 'worker'
  beat_at     timestamptz NOT NULL
);

CREATE TABLE undo_action (                  -- D-22
  token       text PRIMARY KEY,             -- 22-char urlsafe random
  actor       text NOT NULL,
  kind        text NOT NULL,                -- 'habit_skip', 'task_progress', …
  inverse     jsonb NOT NULL,               -- {"service": "habits.unskip", "args": {...}}
  label       text NOT NULL,                -- toast text
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz
);

CREATE TABLE idempotency_key (              -- offline replay safety (NFR-8)
  key            text PRIMARY KEY,
  method         text NOT NULL,
  path           text NOT NULL,
  status_code    integer NOT NULL,
  response_body  jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now()   -- purge after 48h
);

CREATE TABLE push_subscription (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  endpoint    text NOT NULL UNIQUE,
  p256dh      text NOT NULL,
  auth        text NOT NULL,
  user_agent  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  last_ok_at  timestamptz,
  failures    integer NOT NULL DEFAULT 0
);

CREATE TABLE notification_log (             -- de-dupe: "exactly one reminder" (OVL-3)
  id          bigserial PRIMARY KEY,
  type        text NOT NULL CHECK (type IN ('block_start','prayer','plan_approval','overload','alert','magic_link')),
  dedupe_key  text NOT NULL UNIQUE,         -- e.g. 'overload:<task_id>:2026-11-28'
  channel     text NOT NULL,                -- push | discord | email
  payload     jsonb NOT NULL,
  sent_at     timestamptz NOT NULL DEFAULT now(),
  ok          boolean NOT NULL,
  error       text
);

CREATE TABLE secret (                       -- D-18 encrypted UI-entered secrets
  name        text PRIMARY KEY,             -- google_client_secret | notion_token | llm_api_key | vapid_private_key | discord_webhook | healthcheck_url | smtp_password
  value_enc   bytea NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notion_mirror_state (
  entity_type     text NOT NULL,            -- task | habit | settings | placement_history
  entity_id       text NOT NULL,
  notion_page_id  text NOT NULL,
  content_hash    text NOT NULL,
  synced_at       timestamptz NOT NULL,
  PRIMARY KEY (entity_type, entity_id)
);

CREATE TABLE backup_run (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  kind        text NOT NULL CHECK (kind IN ('notion_mirror','restore_dry_run','restore_apply','pg_dump')),
  status      text NOT NULL CHECK (status IN ('running','ok','failed')),
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  stats       jsonb NOT NULL DEFAULT '{}',
  diff        jsonb,                        -- restore dry-run result
  error       text
);
```

---

## 3. Settings sections (`app_setting.section` → Pydantic model)

Implement each as a Pydantic model in `backend/src/scheduler/services/settings_models.py`.
Defaults live **only** in `seed/defaults.py`. Every field below lists its default.

```python
class GeneralSettings(BaseModel):          # section "general"
    timezone: str = "Asia/Kolkata"         # FR-6
    week_starts_on: int = 1                # ISO weekday (1=Mon) for the Week grid
    onboarded_steps: dict[str, bool] = {}  # WEB-27 / BE-25: google, location, office_hours, calendars_habits
    theme: Literal["system","dark","light"] = "system"

class PrecedenceSettings(BaseModel):       # "precedence" — SET-5
    order: list[Literal["meetings","prayers","office_hours","pinned","habits","tasks","backlog"]] = \
        ["meetings","prayers","office_hours","pinned","habits","tasks","backlog"]
    # validator: must be a permutation of all 7; 'backlog' must be last (it never schedules)

class DayHours(BaseModel):
    office: TimeRange | None               # None = no office that day
    earliest_block: time
    latest_block_end: time

class WorkingHoursSettings(BaseModel):     # "working_hours" — SET-7, OFF-1
    days: dict[int, DayHours]              # keys 1..7
    # defaults: Mon–Fri office 10:00–18:30; all days earliest 05:00, latest_block_end 23:00
    #           Sat/Sun office None

class BlockRulesSettings(BaseModel):       # "block_rules" — SET-8
    min_chunk_min: int = 30                # D-05
    max_chunk_min: int = 180
    slot_granularity_min: int = 5          # D-26: validator ge=5, multiple of 5
    planning_window_days: int = 14         # FR-5
    buffers_by_effort: dict[str, int] = {"high": 15, "medium": 10, "low": 0}  # FR-4 (keys = effort vocab keys)
    auto_apply_safe: bool = True           # RPL-4 — owner opted in (D-14); toggle in review header
    auto_apply_creates: Literal["when_safe","never"] = "when_safe"   # D-14
    safe_create_lead_min: int = 60         # D-14 rule 4: new blocks starting sooner always ask
    ask_before_cross_day_moves: bool = True
    streak_break_threshold: int = 3        # HAB-7
    shrink_mode: Literal["minimal"] = "minimal"   # only mode; kept for display/compat
    placement_order: Literal["earliest_first","deadline_first"] = "earliest_first"  # D-09
    replan_debounce_sec: int = 2           # D-29: coalesce bursts, then re-plan at once

class PrayerConfig(BaseModel):
    name: Literal["fajr","dhuhr","jummah","asr","maghrib","isha"]
    enabled: bool = True
    mode: Literal["fixed","computed"]
    fixed_time: time | None                # required when mode=fixed
    computed_offset_min: int = 0           # added to the AlAdhan time when mode=computed
    duration_min: int
    window_start_offset_min: int           # relative to anchor (can be negative)
    window_end_offset_min: int
    edge_min: int = 10                     # PRY-2
    notify_lead_min: int = 0               # adhan push at start (SET-11 has the global lead too)

class PrayerSettings(BaseModel):           # "prayers" — SET-6, PRY-*
    location_name: str | None = None       # set during onboarding (WEB-27 step 2); never shipped as a default
    latitude: float | None = None
    longitude: float | None = None
    # While the location is unset, fixed-time prayers are still placed, but computed prayers
    # (e.g. Maghrib) cannot be generated: BE-12 raises flag PRAYER_LOCATION_MISSING, shown in Decisions.
    method_id: int = 1                     # AlAdhan `method` id (1 = University of Islamic Sciences, Karachi)
    madhab: Literal["shafi","hanafi"] = "hanafi"   # sent as AlAdhan `school` (0=shafi, 1=hanafi)
    # Reserved for the deferred calculation options (D-35 addendum, IN-07 table): optional,
    # defaulted to the API's own defaults when they are added — `latitude_adjustment_method`,
    # `tune`, `shafaq`, `midnight_mode`. Do NOT add them before IN-07's follow-up: they are not
    # part of the settings contract yet and nothing should read them.
    jummah_overrides_dhuhr: bool = True
    qada_rule: Literal["after_isha"] = "after_isha"   # PRY-4 (only option)
    qada_cap_per_day: int = 5
    qada_gap_min: int = 0
    meeting_gap_min: int = 5               # D-07
    drift_threshold_min: int = 10          # PRY-8
    prayers: list[PrayerConfig]            # defaults below
```

Default prayers (PRY-1; windows chosen so the preferred time sits sensibly in the window; the
owner tunes them):

| name | mode | fixed_time | duration | window start / end offset | edge |
|---|---|---|---|---|---|
| fajr | fixed | 05:15 | 30 | −10 / +50 | 10 |
| dhuhr | fixed | 13:00 | 30 | 0 / +60 | 10 |
| jummah | fixed | 12:45 | 60 | −15 / +75 | 10 |
| asr | fixed | 15:35 | 25 | −5 / +70 | 10 |
| maghrib | computed | — (offset 0) | 20 | 0 / +40 | 10 |
| isha | fixed | 19:45 | 45 | −15 / +75 | 10 |

```python
class CalendarRoutingSettings(BaseModel):  # "calendars" — SET-2..4
    prayers_calendar_id: UUID | None = None
    qada_calendar_id: UUID | None = None   # None = same as prayers
    habits_calendar_id: UUID | None = None
    fallback_task_calendar_id: UUID | None = None   # NOT used to guess (SET-3); only offered as a quick-pick
    all_day_events_busy: bool = False
    seed_names: dict[str, str] = {         # used once at discovery to map names → ids
        "prayers": "Prayers", "habits": "Tasks & Todos"}

class HabitDefaults(BaseModel):            # "habit_defaults" — SET-9
    min_min: int = 30
    compressible: bool = True
    not_before: time = time(6, 0)
    not_after: time = time(22, 0)
    priority_key: str = "medium"

class TaskDefaults(BaseModel):             # "task_defaults" — SET-10
    subject_key: str | None = None
    priority_key: str | None = None        # None = must be chosen (gate stays honest)
    effort_key: str = "medium"
    split_key: str = "auto"
    inference: InferenceRules              # defined below; subject keywords live in vocab subject meta

class NotificationType(BaseModel):
    enabled: bool = True
    lead_min: int = 0

class NotificationSettings(BaseModel):     # "notifications" — SET-11, UX-8
    block_start: NotificationType = NotificationType(lead_min=5)
    prayer: NotificationType = NotificationType(lead_min=0)
    plan_approval: NotificationType = NotificationType()
    overload: NotificationType = NotificationType()
    overload_reminder_time: time = time(8, 0)       # OVL-3 "next morning"
    quiet_hours: TimeRange | None = TimeRange(start=time(23, 0), end=time(5, 0))  # prayer pushes ignore quiet hours
    channels: list[Literal["push","discord"]] = ["push"]

class BackupSettings(BaseModel):           # "backup" — SET-12
    notion_enabled: bool = False
    notion_parent_page_id: str | None = None
    mirror_frequency: Literal["after_apply","hourly","daily"] = "after_apply"
    retention_days: int = 14               # NFR-5
    pg_dump_to_drive: bool = False
    notion_ids: dict[str, str] = {}        # created by IN-08: {"tasks_db": …, "habits_db": …, "history_db": …, "settings_page": …}

class AgentSettings(BaseModel):            # "agent"
    default_rate_limit_per_hour: int = 200
    default_daily_cap: int = 500
    default_batch_max: int = 100

class LlmSettings(BaseModel):              # "llm" — CAP-7
    enabled: bool = False
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_sec: int = 20

class GoogleSettings(BaseModel):           # "google" — SET-1
    client_id: str | None = None           # secret goes in `secret` table
    redirect_uri: str | None = None        # None = APP_BASE_URL + /api/google/callback
    sync_interval_min: int = 5             # D-29: fallback polling; push webhooks are primary

class MonitoringSettings(BaseModel):       # "monitoring" — NFR-3/4
    hourly_plan_grace_min: int = 5
    loud_after_consecutive_misses: int = 3
    # Healthchecks ping URL and Discord webhook are secrets (table `secret`), edited in
    # Settings → Monitoring (WEB-24), not stored here.

class TimeRange(BaseModel):                # shared helper type
    start: time
    end: time                              # may be < start (crosses midnight), e.g. quiet hours 23:00–05:00

class InferenceRules(BaseModel):           # used by the capture parser (BE-22, WEB-14)
    priority_words: dict[str, list[str]] = {"high": ["high","urgent","p1","!!"],
                                            "medium": ["med","medium","p2"],
                                            "low": ["low","p3"]}
    deadline_phrases: list[str] = ["before","by","due"]   # followed by a day word or date
    deadline_time: time = time(23, 59)
    estimate_from_last_similar: bool = True

# Non-scheduling technical timeouts (undo 15 s, magic link 15 min, OAuth state 10 min, token
# refresh 5 min, retry backoff) live in `scheduler/constants.py`, which the no-magic-numbers
# lint allow-lists. They are not user preferences.
```

`AppSettings` = all sections + the vocab lists, assembled by `get_settings()`, cached per
request.

---

## 4. Vocabulary seed (`vocab_item`)

| kind | key | label | sort | meta |
|---|---|---|---|---|
| priority | high | High | 1 | `{"rank": 3, "color": "purple"}` |
| priority | medium | Med | 2 | `{"rank": 2, "color": "blue"}` |
| priority | low | Low | 3 | `{"rank": 1, "color": "gray"}` |
| effort | high | High | 1 | `{"office_hours_allowed": false}` |
| effort | medium | Medium | 2 | `{"office_hours_allowed": true}` |
| effort | low | Low | 3 | `{"office_hours_allowed": true}` |
| split_mode | atomic | Atomic | 1 | `{"behaviour": "atomic"}` |
| split_mode | subtasks | Subtasks | 2 | `{"behaviour": "subtasks"}` |
| split_mode | auto | Auto | 3 | `{"behaviour": "auto"}` |
| subject | cybersec | cybersec | 1 | `{"default_calendar": "Learnings", "default_priority": "high", "default_effort": "high", "keywords": ["cyber","cybersec","recon","enumeration","portswigger","burp"]}` |
| subject | sys_design | sys design | 2 | `{"default_calendar": "Learnings", "default_priority": "high", "default_effort": "high", "keywords": ["system design","sys design","sharding","caching","rate limit"]}` |
| subject | arabic | Arabic | 3 | `{"default_calendar": "Arabic", "default_priority": "medium", "keywords": ["arabic"]}` |
| subject | personal | personal | 4 | `{"default_calendar": "Family", "default_priority": "low", "keywords": ["call","family","home"]}` |
| subject | fun | fun | 5 | `{"default_calendar": "Fun/Entertainment/Trips", "default_priority": "medium", "keywords": ["trip","movie","goa"]}` |
| subject | admin | admin | 6 | `{"default_calendar": null, "default_priority": "low", "keywords": ["renew","fix","template","admin"]}` |

- `meta.default_calendar` holds a **calendar name** until discovery runs, after which the seeder
  rewrites it to `default_calendar_id` (uuid) when a calendar with that summary exists. If
  none exists, it stays unresolved and capture leaves `calendar_id` NULL (→ flag, SET-3).
- `effort` buffer minutes live in `block_rules.buffers_by_effort` keyed by effort key. Adding an
  effort level in the UI must add a buffer entry (default 0) in the same transaction.
- `split_mode.meta.behaviour` ∈ {atomic, subtasks, auto} is the **engine** meaning; new split
  modes can only reuse one of these three behaviours (UI shows a select).

---

## 4A. Development calendars

With `FAKE_GOOGLE=1`, the fake calendar port (IN-04) starts with these calendars, so the walking
skeleton can plan and apply before real Google exists (M3): `Work` (role reader → seeded
`read_meetings=true`), `Prayers`, `Learnings`, `Family`, `Fun/Entertainment/Trips`, `Arabic`,
`Tasks & Todos` (owner → `writable=true`). `scheduler-cli seed --dev-calendars` runs discovery
(IN-03 step 1–2) against the fake port and resolves routing by name.

## 5. Work packages

### DB-01 — ORM base, mixins, migration 0001 (all tables)
**Depends on:** F-02, F-04  **Size:** L
**Files:** `backend/src/scheduler/models/{base,settings,auth,agent,google,calendar,task,habit,prayer,placement,plan,log,infra}.py`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial.py`
**Steps:**
1. `models/base.py`: `class Base(DeclarativeBase)`, `TimestampMixin`, `AttributionMixin` (§1).
2. Write one ORM class per table in §2 with exact column names/types. Use `Mapped[...]` +
   `mapped_column`. CHECK constraints via `__table_args__`.
3. Alembic `env.py` reads `DATABASE_URL` from `scheduler.config`; `target_metadata = Base.metadata`.
4. Generate 0001 with `alembic revision --autogenerate`, then **hand-edit** to add:
   `CREATE EXTENSION IF NOT EXISTS btree_gist;`, the
   exclusion constraint, and the partial unique indexes (autogenerate misses these).
5. Note the forward reference `task.import_batch_id → import_batch` and
   `placement.created_plan_run_id → plan_run`: create referenced tables first in the migration.
**Tests:** `tests/services/test_schema.py`:
- inserting two overlapping active non-pinned placements raises `IntegrityError` (exclusion);
- overlapping when one is pinned → OK;
- two `plan_run` rows with `status='proposed'` → `IntegrityError`;
- `habit` with `min_min > ideal_min` → `IntegrityError`.
**Done when:** `make migrate` on an empty DB succeeds, `alembic downgrade base` succeeds, tests green.

### DB-02 — Settings models & seeder
**Depends on:** DB-01  **Size:** M
**Files:** `services/settings_models.py`, `seed/defaults.py`, `seed/seeder.py`, `cli.py` (`seed` command)
**Steps:**
1. Implement every model in §3 with the defaults in `seed/defaults.py` (models themselves
   should declare no defaults other than via `defaults.py` constants — import them).
2. `seeder.seed(session)`: idempotent. Insert each missing `app_setting` section with
   `updated_by='system'`; insert missing vocab items (§4); create the `user_account` from
   `OWNER_EMAIL` if absent. **Never overwrite existing rows** (the README's rule 8: defaults are
   seeded once, never consulted again).
3. Run the seeder automatically at API and worker startup (after migrations check).
**Tests:** seeding twice yields identical row counts; editing a setting then reseeding keeps the edit.
**Done when:** `scheduler-cli seed` prints a summary of inserted vs existing rows.
