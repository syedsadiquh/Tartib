# 06 — Worker, Jobs, Notifications & Watchdog

One process: `python -m scheduler.worker` (container `worker`). It runs two loops in threads:
1. **APScheduler `BlockingScheduler`** (tz = settings tz) for timed jobs.
2. **Queue poller** draining the `job` table.

The API process never runs schedules (D-04). If the worker dies, the external dead-man check
(WK-05) alerts — this is the historical failure mode (NFR-4).

---

### WK-01 — Job queue
**Depends on:** DB-01 **Size:** M
**Files:** `worker/__init__.py`, `worker/__main__.py` (entry for `python -m scheduler.worker`: starts the poller thread + scheduler), `worker/queue.py`, `services/jobs.py` (enqueue side, used by API)
**Enqueue:**
```python
def enqueue(session, kind, payload={}, *, run_after=None, dedupe_key=None, max_attempts=3) -> None
    # INSERT … ON CONFLICT (dedupe_key) WHERE status = 'queued' AND dedupe_key IS NOT NULL
    #   DO UPDATE SET run_after = GREATEST(job.run_after, EXCLUDED.run_after), payload = EXCLUDED.payload
    # (the WHERE must repeat the full index predicate or Postgres can't use the partial index;
    #  GREATEST = debounce: a burst of edits keeps pushing the run later)
def enqueue_replan(session, trigger, debounce_sec):
    enqueue(session, "replan", {"trigger": trigger}, run_after=now+debounce, dedupe_key="replan")
    # coalesces bursts: a second edit inside the window just pushes run_after (debounce)
```
**Poll loop (every 1 s, D-29; drain up to 10 jobs per tick before sleeping):**
```sql
UPDATE job SET status='running', started_at=now(), attempts=attempts+1
WHERE id = (SELECT id FROM job WHERE status='queued' AND run_after <= now()
            ORDER BY run_after FOR UPDATE SKIP LOCKED LIMIT 1)
RETURNING *;
```
Dispatch by `kind` to a handler registry. Success → `done`. Exception → if attempts < max:
`queued`, `run_after = now + 30s * 2^attempts`; else `failed` + alert (warn). Purge `done` jobs
older than 7 days nightly.
**Handlers:** `replan`, `apply_plan` (auto-apply path), `sync_calendars`, `discover_calendars`,
`notion_mirror`, `push` (single notification), `materialize_recurrences`, `alert`.
**Tests:** SKIP LOCKED with two pollers runs each job once; retry backoff; dedupe coalescing.

### WK-02 — Scheduled jobs
**Depends on:** WK-01, BE-13 **Size:** M
Register **only jobs whose handlers already exist**. Each later package (IN-05, WK-03, WK-04,
WK-05, IN-08, BE-24, DP-07) adds its own row to `worker/schedules.py` when it lands.
**Spec:** RPL-1, NFR-3
**Files:** `worker/schedules.py`
| Job | Trigger | Does |
|---|---|---|
| `hourly_plan` | cron minute=0 | `planning.run(trigger='hourly')` |
| `calendar_sync` | every `google.sync_interval_min` (fallback; push webhooks are primary, IN-15) | `calendar_sync.sync_all` |
| `google_watch_renew` | daily 04:00 | IN-15 `ensure_watches()` |
| `prayer_instances` | daily 00:01 + on settings change | ensure 14 days of prayer instances |
| `habit_rollover` | daily 00:05 | WK-03 |
| `recurrences` | hourly :30 | materialise recurring tasks |
| `notifications_tick` | every minute | WK-04 |
| `overload_reminder` | daily at `notifications.overload_reminder_time` | WK-04 (OVL-3) |
| `heartbeat` | every minute | WK-05 |
| `watchdog` | every 5 min | WK-05 |
| `notion_mirror` | per `backup.mirror_frequency` | IN-08 |
| `purge` | daily 03:00 | expired undo/idempotency/magic links/sessions, old jobs, `agent_request_log` > 30 d |
| `pg_dump` | daily 02:30 (if enabled) | DP-07 |

Every scheduled job is wrapped by `run_tracked(job_name, scheduled_for, fn)` which writes
`scheduled_run` (started → ok/failed). APScheduler options: `coalesce=True`,
`misfire_grace_time=300` (NFR-3 "within 5 minutes"), `max_instances=1`.
**Tests:** `run_tracked` writes rows; a raised exception marks failed and alerts.

### WK-03 — Nightly habit rollover (misses)
**Depends on:** BE-11 **Size:** S
**Spec:** HAB-9, D-17
For yesterday (local date) and each active habit due yesterday (weekday ∈ weekdays, date ≥
active_from): if occurrence missing or `scheduled` → set `missed` via `streaks.on_missed`
(activity + engine_log `category=system`, title "Gym missed — streak reset"). Idempotent.
Also: occurrences for ended/archived habits are never marked missed (HAB-11).
**Tests:** done/skipped untouched; missed resets streak, habit stays active; runs twice = same result.

### WK-04 — Notifications dispatcher (exactly four kinds)
**Depends on:** IN-10, IN-11 **Size:** M
**Spec:** UX-8, SET-11, OVL-3
`notifications_tick` (every minute):
1. **block_start** — active placements (task chunks, habits) with
   `start_at - lead ∈ (now-60s, now]` → push "LR1: Limits starts in 5m". Dedupe
   `block_start:<placement_id>:<start>`. Respect quiet hours.
2. **prayer** — prayer/qada placements with `start_at - lead ∈ (now-60s, now]` → "Asr · 15:35".
   **Ignores quiet hours** (prayers outrank). Dedupe `prayer:<instance>:<start>`.
3. **plan_approval** — enqueued by planning when a run has `ask` changes; dedupe key =
   `plan_approval:` + sha1 of the sorted ask change ids (so an hourly re-run that proposes the
   same changes does not push again);
   suppressed in quiet hours (sent at quiet-hours end if still pending). Tag `plan-approval`.
4. **overload** — at `overload_reminder_time` daily: for each task with an overload flag code
   (`TASK_PARTIAL_FLAGGED|TASK_NO_SLOT|TASK_ATOMIC_NO_FIT`) where `flag_raised_at::date < today`
   (`(flag_raised_at AT TIME ZONE <settings tz>)::date < today` — never cast in the session tz)
   and `flag_reminded_on IS NULL` → one push "W2D4 still 30m short", set `flag_reminded_on=today`.
   **Exactly one reminder per flag, ever** (A8). A cleared and re-raised flag resets
   `flag_reminded_on` (new flag).
Delivery: channels from settings (`push`, `discord`). Every attempt → `notification_log`.
**Tests:** A8 — flag raised Thu, run reminder Fri 08:00 → one push; Fri 09:00 and Sat 08:00 → none;
quiet hours suppress block_start but not prayer.

### WK-05 — Heartbeat, watchdog, readiness
**Depends on:** WK-02, IN-11 **Size:** S
**Spec:** NFR-3, NFR-4
1. `heartbeat` (every minute): upsert `heartbeat('worker', now)`; GET `HEALTHCHECK_PING_URL`
   (Healthchecks.io: period 5 min, grace 5 min → it alerts by email/Discord if the box or the worker is dead).
2. `watchdog` (every 5 min): for `hourly_plan`, expected run = last full hour; if no
   `scheduled_run` with status ok/failed for it and now > expected + `hourly_plan_grace_min` →
   insert `missed` row and alert **warn**; if the last `loud_after_consecutive_misses` expected
   runs are all missed/failed → alert **loud**. Same for `calendar_sync` (stale if last ok > 3× interval).
   Google token `revoked` → loud alert once per day.
3. `GET /api/health/ready` (API) → 200 only if DB reachable, migrations at head, worker
   heartbeat < 3 min old; else 503 with reasons. Caddy/Uptime checks can use it.
**Tests:** simulated missed hours produce warn then loud; readiness 503 when heartbeat stale.
