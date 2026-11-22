# 05 — Integrations

All external I/O lives in `backend/src/scheduler/integrations/`. Each integration exposes a
small **port** (Protocol) so services and tests can swap in a fake. Fakes are first-class code,
not test-only: `FAKE_GOOGLE=1` makes the whole app run end-to-end without Google.

---

### IN-01 — Crypto & secrets store
**Depends on:** DB-01 **Size:** S
**Spec:** NFR-6, D-18
**Files:** `integrations/crypto.py`, `services/secrets.py`
**Steps:**
1. `encrypt(bytes) -> bytes`, `decrypt(bytes) -> bytes` with `Fernet(APP_ENCRYPTION_KEY)`.
2. `secrets.get(session, name) -> str | None`: DB `secret` row (decrypted) → else env var fallback
   (`google_client_secret`→`GOOGLE_CLIENT_SECRET`, etc.).
3. `secrets.set(session, name, value, actor)` → encrypt + upsert + audit (`after` = `"••••" + last 4`).
4. API: `PUT /api/settings/secrets/{name} {value}` (user only), `GET /api/settings/secrets` → names + `is_set` + source (`db|env|none`). Never return values.
**Tests:** round-trip; wrong key → clear error; GET never leaks value.

---

## Google Calendar

### IN-02 — OAuth connect / status / disconnect
**Depends on:** IN-01, BE-19 **Size:** M
**Spec:** SET-1, NFR-6
**Files:** `integrations/google/oauth.py`, `api/routers/google.py`
**Scopes:** `https://www.googleapis.com/auth/calendar` (read+write events and list calendars),
`openid`, `email`. (If later adding Drive pg_dump: `drive.file`.)
**Flow:**
1. `POST /api/google/connect` → build flow with client id (settings.google.client_id or env) and
   secret (secrets), redirect URI (`settings.google.redirect_uri` or `APP_BASE_URL/api/google/callback`),
   `access_type=offline`, `prompt=consent`, PKCE; store `oauth_state`; return `{auth_url}`.
   The UI navigates there.
2. `GET /api/google/callback?state&code` → verify state (≤10 min old), exchange code, read
   email from id_token, upsert `google_account` (encrypted tokens, scopes, status connected),
   audit `connect`, enqueue `discover_calendars` + `sync_calendars`, redirect to
   `/settings/google?connected=1`.
3. `GET /api/google/status` → `{connected, email, scopes, status, token_expires_at, last_ok_at,
   last_error, redirect_uri}` (token health, SET-1).
4. `POST /api/google/disconnect {confirm: true}` → revoke token at Google (best effort), delete
   row, audit; placements keep their event ids (the user chooses to delete events separately).
5. `get_credentials(session)` refreshes access tokens when < 5 min left; on `invalid_grant` set
   status `revoked`, raise `GoogleAuthError` → alert (WK-04) and UI banner "Re-authorize".
**Tests:** state mismatch → 400; refresh path updates encrypted access token; invalid_grant → status revoked.

### IN-03 — Calendar discovery & routing
**Depends on:** IN-02 **Size:** M
**Spec:** SET-2, SET-3, SET-4
**Files:** `integrations/google/calendars.py`, `services/calendars.py`, `api/routers/calendars.py`
**Steps:**
1. `discover()` → `calendarList.list` (all pages). Upsert `calendar` rows by
   `google_calendar_id` (summary, color, access_role). New calendars default to
   `read_meetings=false, writable=false` — **no guessing**. The onboarding screen (WEB-27) and
   Settings → Calendars ask the user to tick which calendars feed meetings (e.g. the read-only
   work calendar) and which may be written.
2. First discovery only: resolve `vocab subject.meta.default_calendar` names and
   `calendars.seed_names` to ids by exact summary match (case-insensitive). Unresolved names stay
   unresolved (shown as "no calendar — unrouted" in the routing table).
3. `GET /api/calendars` → list with routing info; `PATCH /api/calendars/{id}
   {label?, read_meetings?, writable?, treat_as_busy?, enabled?}` (writable requires role
   owner/writer → 422).
4. Routing table endpoint data (mockup web/07 middle): `GET /api/calendars/routing` →
   rows: prayers, qada, habits (from settings) + one row per subject (from vocab meta) with
   `calendar_id|null`. Editing routes = `PATCH /api/settings/calendars` or `PATCH /api/vocab/subject/{id}`.
**Tests:** discovery idempotent; seed-name resolution; non-writer can't be writable.

### IN-04 — Calendar port, Google client, fake client
**Depends on:** IN-01 (port + fake); the real client is only exercised after IN-02 **Size:** M
**Files:** `integrations/google/port.py`, `integrations/google/client.py`, `integrations/google/fake.py`
```python
class CalendarPort(Protocol):
    def list_calendars(self) -> list[CalendarInfo]: ...
    def list_events(self, cal_id: str, *, sync_token: str | None, time_min: datetime | None,
                    time_max: datetime | None) -> EventPage: ...
        # always singleEvents=True (recurring meetings expanded into instances; works with sync
        # tokens) and showDeleted=True; handles pagination; returns next_sync_token.
        # All-day events: start.date/end.date → start_at = local midnight of start.date,
        # end_at = local midnight of end.date (exclusive), all_day=True.
    def insert_event(self, cal_id: str, ev: EventBody) -> EventRef: ...      # EventRef(id, etag)
    def patch_event(self, cal_id: str, event_id: str, ev: EventBody) -> EventRef: ...
    def delete_event(self, cal_id: str, event_id: str) -> None: ...          # 404/410 = success
    def move_event(self, src_cal: str, event_id: str, dst_cal: str) -> EventRef: ...
```
`EventBody`: `summary, description, start, end (dateTime + timeZone=settings tz), colorId?,
transparency='opaque', reminders={'useDefault': False}` (the app sends its own pushes; avoid
double alerts), `extendedProperties.private = {"sch_app": "1", "sch_key": group_key,
"sch_pid": placement_id, "sch_kind": block_kind, "sch_fp": sha1(start_iso|end_iso)[:16]}` (CAL-2
ownership marker; `sch_fp` = the times **the app** wrote, used by IN-05 to tell our writes from user moves).
Summary formats: task chunk `"{title}"` (+ `" (2/4)"` when chunk_count>1); habit `"{name}"`
(+ `" · {n}m"` when compressed); prayer `"{Label}"`; qada `"Qada — {Label}"`.
Description: `"Scheduled by Tartib · {rule title}\nWhy: {reason}\nOpen: {APP_BASE_URL}/tasks/{id}"`.
Real client: `googleapiclient.discovery.build('calendar','v3', credentials=…, cache_discovery=False)`;
wrap `HttpError` → `GoogleApiError(status, reason, retryable = status in (429, 500, 502, 503, 504))`.
Exponential backoff inside a single "try" for 429 (max 3 tries / 8 s). Fake client: in-memory dict
per calendar, supports sync tokens (monotonic counter), `fail_next(n, op)` hook for tests.
Factory `get_calendar_port(session)` → fake if `FAKE_GOOGLE=1`.
**Tests:** fake implements the Protocol (mypy); sync token semantics; failure injection.

### IN-05 — Inbound sync (meetings + user edits in Google)
**Depends on:** IN-03, IN-04 **Size:** L
**Spec:** OFF-2, CAL-2, CAL-3, RPL-1 (calendar change trigger)
**Files:** `services/calendar_sync.py`, route `POST /api/sync/calendar`
**Algorithm `sync_all(session)`** (worker job every `google.sync_interval_min`, and on demand):
```
for cal in calendars where enabled and (read_meetings or writable):
    page = port.list_events(cal.google_id, sync_token=cal.sync_token,
                            time_min = None if sync_token else now - 1 day,
                            time_max = None if sync_token else now + window + 1 day)
    on 410 GONE: cal.sync_token = None; retry once with full window
    changed_any = False
    for ev in page.events:
        if ev.extendedProperties.private.sch_app == "1":     # our own event
            handle_owned(ev); continue
        if cal.read_meetings: upsert/delete external_event; changed_any = True
    cal.sync_token = page.next_sync_token; cal.last_synced_at = now
if changed_any or owned_changes: enqueue replan(trigger='calendar_change')

handle_owned(ev):
    p = placement by sch_pid (fallback google_event_id)
    if ev.status == 'cancelled':
        if p active: user deleted it in Google →
            task chunk: mark placement removed (owner user); activity "deleted in Google";
                        the task's remaining goes back to the pool (no penalty)
            habit:      treat as skip of that occurrence? NO — treat as removal only; occurrence stays
                        'scheduled' and the next plan proposes it again. (Conservative; log it.)
            prayer:     re-create on next apply (prayers are not optional); log.
        return
    if sha1(ev.start|ev.end)[:16] != ev.private.sch_fp:      # times differ from what WE wrote
        # CAL-3: a block the user moved in Google is treated as pinned
        p.start_at/end_at = ev times; p.owner='user'; p.pinned=True
        activity "moved in Google → pinned"; engine_log PINNED_LEFT_ALONE (category 'pin')
```
`sync_all` takes the same advisory lock as planning/apply (`pg_advisory_xact_lock(hashtext('plan'))`)
so it never observes a half-finished apply.
**Orphans** (events with `sch_app==1` whose `sch_pid` matches no placement): never deleted directly.
They are recorded in `calendar_orphan(google_event_id, calendar_id, start_at, end_at, summary)`
(add to migration) and the next plan run emits a `delete` change for each (reason
`PRECLEAN_ORPHAN`, class **ask**), so the user approves it. The orphan scan is **disabled** while
`backup_run` of kind `restore_apply` is running or until its post-restore re-attach finished
(IN-09), because right after a restore every event looks orphaned.
**Tests (fake port):** new meeting → external_event + replan enqueued; declined meeting ignored as
obstacle; user moved our event → placement pinned; 410 → full resync; orphan cleaned.

### IN-06 — Outbound writer with rollback
**Depends on:** IN-04 **Size:** M
**Spec:** RPL-5, CAL-4
**Files:** `services/calendar_writer.py`
```python
class Journal: entries: list[JournalEntry]   # op, cal_id, event_id, before: EventBody | None
def execute(ops: list[Op], port) -> Journal       # raises ApplyFailed(journal, op, error)
def rollback(journal, port) -> list[str]          # returns errors that could not be undone
```
Each op: try → on `GoogleApiError` (any) retry **once** after 1 s → on second failure raise
`ApplyFailed`. `rollback` processes the journal in reverse: created→delete; patched→patch back to
`before`; deleted→insert `before`. Re-inserted events get new ids: `rollback` returns `{placement_id: new_event_id}` and
BE-14 writes those ids in a **separate small transaction** (the plan's own DB changes are still
never committed). If rollback itself fails, alert loudly with the list — "never leave a
half-applied plan" means we always attempt and always alert. Calendar change of a placement (routing changed) uses `move_event`.
**Tests:** inject failure at op k for k in 1..n; assert fake calendar state equals pre-state after rollback.

---

## Prayer times

### IN-07 — Prayer time computation & drift guard
**Depends on:** DB-02 **Size:** M
**Spec:** PRY-1, PRY-8, SET-6
**Files:** `integrations/prayer_times.py`, `integrations/solar.py`
**Steps:**
1. `library_times(d: date, settings) -> dict[name, datetime]` using `adhanpy`. **Check the
   installed version's README/signature before writing the call** (the API differs across
   versions). Expected shape:
   `params = CalculationMethod[settings.method].parameters` (or `CalculationParameters(method=…)`),
   `params.madhab = Madhab.HANAFI|SHAFI`, `PrayerTimes((lat, lon), datetime(d), calculation_parameters=params, time_zone=ZoneInfo(tz))`.
   Pin the result with a regression test for a fixed public test location (Kolkata, 22.5726, 88.3639) on 3 fixed dates so a library upgrade
   that changes behaviour fails loudly. Convert results to the settings tz.
2. `crosscheck_times(d, settings) -> dict[name, datetime]`: in-house NOAA solar position
   implementation (`solar.py`, ~80 lines: declination, equation of time, hour angle for
   sunset/sunrise and for the method's Fajr/Isha angles, Asr shadow factor 1 (shafi) or 2 (hanafi)).
   Karachi method: Fajr 18°, Isha 18°.
3. For each **computed** prayer: anchor = library + `computed_offset_min`;
   `drift_min = |library − crosscheck|`; `drift_flag = drift_min > drift_threshold_min`.
4. For fixed prayers, also compute library time for display ("computed ±10") but no drift flag.
5. Cache per (date, settings hash) in-process.
**Tests:** known values for the Kolkata test location (22.5726, 88.3639) on a few dates — sunset/maghrib within 2 min
between both methods; forced bad longitude in crosscheck → drift_flag true.

---

## Notion (bookkeeper)

### IN-08 — Notion write-only mirror
**Depends on:** IN-01, BE-14 **Size:** L
**Spec:** NOT-1, NOT-2, SET-12, 04-deployment §5 (mirror habits, streaks, settings too)
**Files:** `integrations/notion/client.py`, `services/notion_mirror.py`
**Layout created under `backup.notion_parent_page_id` on first run (ids stored in settings
`backup.notion_ids`):**
- Database **Tasks**: Title (title), Task ID (rich_text), Est (number), Priority (select),
  Deadline (date), Effort (select), Split (select), Subject (select), Calendar (rich_text),
  State (select), Subtasks (rich_text JSON), Depends On (relation → Tasks), Created By (rich_text),
  Updated (date).
- Database **Habits**: Name, Habit ID, Weekdays (multi_select), Ideal, Min, Window (rich_text),
  Ideal Time, Priority, Compressible (checkbox), State, Streak, Best, Consecutive Skips.
  The occurrence history (`[["2026-11-20","d",60], …]`) goes in the **page body** as code
  blocks; Notion limits one rich-text object to 2 000 characters, so split the JSON into ≤ 2 000-char
  pieces (≤ 100 pieces per block, more blocks if needed) and re-join on restore.
- Database **Placement History**: append-only rows `{ts, entity, title, from, to, rule, actor}`
  from `engine_log` category apply/pin since last mirror (NOT-2 "append-only log").
- Page **Settings snapshot**: export JSON (BE-19) in page-body code blocks, chunked the same way, replaced each mirror.
- Task **Subtasks** property: if the JSON exceeds 2 000 chars, store it in the page body instead (property holds `"see body"`).
**Algorithm:** for each entity compute `content_hash` of the mirrored fields; skip when equal to
`notion_mirror_state.content_hash`; else create/update page. Respect Notion rate limit (3 req/s:
sleep 0.35 s between calls; on 429 honour `Retry-After`). Record `backup_run`. Runs as job
`notion_mirror` after every apply (debounced 60 s) or per `mirror_frequency`.
**Never read from Notion here** (NOT-1).
**Tests:** with a fake Notion port — unchanged entities produce zero calls; changed task updates one page.

### IN-09 — Restore from Notion (dry-run first)
**Depends on:** IN-08 **Size:** L
**Spec:** NOT-3, NOT-4, SET-12, A10
**Files:** `services/notion_restore.py`, routes
**Steps:**
1. `POST /api/restore/notion {dry_run: true}` → read all three databases + settings page;
   build the would-be state; diff vs Postgres: per entity `create | update(fields) | unchanged |
   only_in_db`. Store in `backup_run.diff`; return summary + diff (SET-12 "dry-run diff first").
2. `POST /api/restore/notion {dry_run: false, backup_run_id, confirm: true}` → apply in one
   transaction: upsert tasks (same ids), subtasks, dependencies, habits (+ occurrences from the
   JSON; then `streaks.recompute`), settings import (BE-19). **Does not delete** rows that are
   only in DB unless `delete_missing=true`. Placements are not restored (they are derived):
   instead, mark all existing placements whose events still exist in Google as `hints`
   (re-attach by `sch_pid`/`sch_key` via a full sync), then run one plan (`trigger='restore'`)
   and return its plan run id ("re-plan once → review delta").
3. Timing target (NOT-4): ≤ 15 min for 2 000 tasks — paginate Notion queries (100/page).
**Tests:** A10 with fake Notion: wipe DB tables → restore → same task/habit set (ids, fields);
plan produces an equivalent calendar (same blocks as before for unchanged inputs).

---

## Notifications & messaging

### IN-10 — Web Push
**Depends on:** IN-01 **Size:** M
**Spec:** UX-8, SET-11
**Files:** `integrations/push.py`, `api/routers/push.py`
VAPID keys: if no env and no `secret` rows, generate once at startup (`py_vapid`) and store
encrypted. `GET /api/push/vapid-key` → public key. `POST /api/push/test` → sends "Test notification" to all subscriptions, returns per-device result. Subscribe stores endpoint/keys; unsubscribe
deletes. `send(sub, payload: {title, body, url, tag, actions?})` with TTL 300 (prayer: 900); on
404/410 delete the subscription; increment `failures` on others (delete at 5).
Payload `tag` lets the SW replace stale notifications (e.g. `plan-approval`).
Actions (UX-1 "tick from the notification"): habit block start → `actions: [{action:"done",title:"Done"},{action:"skip",title:"Skip"}]`, handled in the SW by calling the API (WEB-26).

### IN-11 — Discord webhook alerts
**Depends on:** IN-01 **Size:** S
**Spec:** NFR-3, NFR-4
`discord.alert(level: info|warn|loud, title, body)` → POST to webhook (secret `discord_webhook`).
`loud` prefixes `@here`. Never raises (log failures). Also used as an optional notification channel.

### IN-12 — LLM client (NL capture only)
**Depends on:** IN-01 **Size:** S
**Spec:** CAP-7, D-19
OpenAI-compatible `POST {base_url}/chat/completions` via httpx with `response_format={"type":"json_object"}`,
temperature 0, timeout from settings. Function `parse_tasks(text, vocab, today) -> list[dict]`.
System prompt (store in `services/capture/prompt.txt`): role, the exact JSON schema, the allowed
vocab keys, today's date + tz, "never invent fields; use null when unsure", examples from the
mockups. Log token usage only (no content).

### IN-14 — Google Drive upload for pg_dump (optional)
**Depends on:** IN-02, DP-07 **Size:** S
Adds scope `https://www.googleapis.com/auth/drive.file` (re-consent shown in Settings → Google
when `backup.pg_dump_to_drive` is switched on). `upload(path, folder_name="Tartib backups")`
creates the folder once (id cached in `backup.notion_ids["drive_folder"]`), uploads with
resumable upload, deletes files older than `retention_days`.

### IN-13 — Email sender (magic link)
**Depends on:** IN-01 **Size:** S
SMTP via stdlib `smtplib` (STARTTLS) using settings/env; dev uses mailpit. If SMTP is not
configured, `POST /api/auth/magic-link` logs "SMTP not configured — use scheduler-cli login-link".

### IN-15 — Google push notifications (two-way, near-instant)
**Depends on:** IN-05, BE-27 **Size:** M
**Spec:** D-29, CAL-3, CAL-4
**Files:** `integrations/google/watch.py`, `api/routers/google.py` (webhook), worker schedule entry
1. `ensure_watches()` (after discovery, on calendar PATCH, and daily): for each enabled calendar
   with `read_meetings or writable`, if no active `calendar_watch` expiring > 48 h from now:
   `events.watch(calendarId, body={id: uuid4, type: "web_hook", address:
   f"{API_PUBLIC_URL}/api/google/webhook", token: <random 32B>, params: {ttl: "604800"}})`; store
   `channel_id, resource_id, token_hash, expires_at`; stop the previous channel (`channels.stop`).
2. `POST /api/google/webhook` (public, no session): read `X-Goog-Channel-ID`,
   `X-Goog-Channel-Token`, `X-Goog-Resource-State`. Unknown channel or token HMAC mismatch → 404
   (don't reveal anything). `sync` state → 200 only. `exists`/`not_exists` → enqueue
   `sync_calendar {calendar_id}` (dedupe `sync:<calendar_id>`, run_after now + 1 s) → 200 fast
   (< 100 ms; Google retries slow endpoints).
3. `sync_calendar` runs IN-05's algorithm for that one calendar; relevant changes enqueue a replan.
4. Fallback: if `ensure_watches` fails with 4xx for the address (e.g. Google rejects the host),
   record `last_error`, alert once (warn), and set the effective polling interval to 1 min until
   a watch succeeds.
5. Disconnect Google → stop all channels.
**Tests:** fake port records watch calls; webhook with a bad token → 404 and nothing queued; good
notification → one sync job; renewal replaces channels expiring within 48 h.
