# 03 — The Scheduling Engine

The engine is the core of the product and the riskiest part to get wrong. It is a **pure
function**:

```
plan(input: PlanInput) -> PlanOutput          # no I/O, no clock, no randomness
diff(current: list[CurrentBlock], output: PlanOutput, input: PlanInput) -> list[Change]
```

Everything here maps to `docs/02-engine-spec.md` and requirements §6–§13. Ambiguities are
settled in `docs/decisions.md` (cited as D-xx).

**Golden rules for implementers**
1. Determinism: never iterate a `set` or `dict` without sorting. Every tie is broken by an
   explicit key that ends in the item's `id`.
2. No constants: every number comes from `input.settings`. (A unit test feeds non-default
   settings and checks they are used.)
3. All datetimes tz-aware. Local date/time math uses `input.tz`.
4. Engine never raises for "can't fit". It returns flags. It raises `EngineInvariantError`
   only when its own output breaks an invariant (a bug).

---

Allowed imports in `engine/` (enforced by F-02's architecture test): `__future__`, `datetime`,
`zoneinfo`, `dataclasses`, `enum`, `uuid`, `hashlib`, `itertools`, `functools`, `collections`,
`heapq`, `bisect`, `math`, `typing`, and `scheduler.engine.*`.

## 1. Module layout (`backend/src/scheduler/engine/`)

| Module | Contents |
|---|---|
| `rules.py` | `RuleCode` enum, `Category` enum, rule → category map, human templates |
| `types.py` | all input/output dataclasses (§4) |
| `timeutil.py` | `Interval`, `IntervalSet`, rounding, local-day helpers (§5) |
| `frames.py` | day frames, office intervals, window days (§6.1) |
| `occupancy.py` | `Occupancy` — the board everything is placed on (§5.3) |
| `prayers.py` | prayer placement, shifting, qada stacking (§6.3) |
| `fixed.py` | meetings, pinned, frozen placement + conflict flags (§6.2, §6.4) |
| `habits.py` | habit occurrence placement (§6.5) |
| `chunking.py` | `next_chunk()` for atomic / subtasks / auto (§6.7) |
| `ordering.py` | task eligibility, sort key, dependency topo-sort (§6.6) |
| `tasks.py` | slot search + hints (§6.8) |
| `shrink.py` | minimal habit shrink (§6.9) |
| `flags.py` | overload report, lever candidates (§6.10) |
| `planner.py` | `plan()` — precedence-driven orchestration (§6.11) |
| `invariants.py` | `check(output, input)` (§7) |
| `diff.py` | `diff()` + `requires` computation (§8) |
| `classify.py` | safe / ask / never (§8.4) |
| `whatif.py` | run variants and compare (§10) |
| `why.py` | builds the "why it landed here" bullets (§6.12) |

---

## 2. Vocabulary inside the engine

- **Rank keys:** `meetings, prayers, office_hours, pinned, habits, tasks, backlog` (from settings).
- **Block kinds:** `meeting`, `prayer`, `qada`, `pinned`, `frozen`, `habit`, `task_chunk`.
- **now_ceil:** `input.now` rounded **up** to the slot granularity in local time. Nothing new
  starts before it.
- **Window:** local dates `today … today + planning_window_days − 1` (FR-5).

---

## 3. Rule codes (`rules.py`)

Every decision and every flag carries exactly one rule code. Category drives the engine-log
filter chips (mockup web/03: All · Shrinks · Held · Prayers · Released).

| Code | Category | Emitted when | Title template (UI) |
|---|---|---|---|
| `PRAYER_PLACED` | prayer | prayer at preferred time | "{prayer} at {time}" |
| `PRAYER_SHIFTED` | prayer | prayer moved inside protected core (PRY-3) | "{prayer} moved {from} → {to}" |
| `PRAYER_QADA` | prayer | core cannot fit → qada after Isha (PRY-4) | "{prayer} → qada after Isha" |
| `PRAYER_QADA_STACKED` | prayer | 2nd+ qada stacked | "{prayer} stacked as qada #{n}" |
| `PRAYER_QADA_CAP` | flag | more qadas than `qada_cap_per_day` | "Qada cap reached on {date}" |
| `PRAYER_QADA_NO_ROOM` | flag | a qada cannot fit between Isha and local midnight | "No room for qada {prayer} on {date} — pray and mark it" |
| `PRAYER_LOCATION_MISSING` | flag | (service-level, BE-12) computed prayer needs a location that isn't set | "Set your location to compute {prayer}" |
| `PRAYER_LOCATION_MISSING` | flag | (service-level, BE-12) computed prayer needs a location that isn't set | "Set your location to compute {prayer}" |
| `PRAYER_DRIFT` | flag | drift flag on input (PRY-8) | "{prayer} drift {n}m — check location/method" |
| `PRAYER_PRAYED_RELEASED` | release | prayed early, tail freed (PRY-6) | "{prayer} prayed at {time} — {n}m freed" |
| `MEETING_FIXED` | placement | meeting registered | — (not logged) |
| `MEETING_CONFLICT` | flag | meeting overlaps a higher-ranked block (only if user reorders) | "Meeting overlaps {other}" |
| `PINNED_LEFT_ALONE` | held | pinned block kept (A9) | "Pinned, engine left alone" |
| `PINNED_CONFLICT` | flag | pinned overlaps a higher-ranked block (D-15) | "{title} overlaps {other}" |
| `HABIT_PLACED` | placement | at ideal time & length | — |
| `HABIT_MOVED` | placement | ideal time taken → nearest free slot in window | "{habit} moved to {time}" |
| `HABIT_FIT_COMPRESSED` | shrink | literal pressure → shorter than ideal, ≥ min | "{habit} fit at {n}m (ideal {ideal}m)" |
| `HABIT_NO_ROOM` | flag | not even min fits in window | "{habit} has no room on {date}" |
| `HABIT_SKIPPED_RELEASED` | release | occurrence skipped → block removed | "{habit} skipped — {time} released" |
| `HABIT_SHRUNK_FOR_TASK` | shrink | minimal shrink (HAB-3) | "{habit} gave up {n} minutes — not {more}" |
| `HABIT_HELD_AT_FLOOR` | held | shrink hit min_min | "{habit} held at floor {min}m" |
| `HABIT_HARD_NOT_COMPRESSED` | held | hard habit was the blocker (HAB-2) | "{habit} is hard — not compressed" |
| `TASK_PLACED` | placement | chunk placed by search | "{task} → {day} {time}" |
| `TASK_KEPT_SLOT` | placement | chunk kept previous slot (D-10) | — |
| `TASK_PLACED_EARLIER_DAY` | placement | placed on a day before the deadline day | — |
| `TASK_PARTIAL_FLAGGED` | flag | some placed, remainder flagged (TSK-5) | "{task}: {placed} placed, {short} short" |
| `TASK_NO_SLOT` | flag | nothing placed | "{task} could not be placed" |
| `TASK_BLOCKED_MISSING_FIELDS` | flag | no estimate or priority (TSK-2, CAP-2) | "{task} needs {fields}" |
| `TASK_BLOCKED_NO_CALENDAR` | flag | calendar missing (SET-3) | "{task} needs a calendar" |
| `TASK_BLOCKED_DEPENDENCY` | flag | dependency not done & not fully placed (D-13) | "{task} waits for {dep}" |
| `TASK_BLOCKED_PINNED` | flag | only slot before deadline is blocked by a pinned block | "{task} blocked by pinned {title}" |
| `TASK_OVERFLOW` | flag | remainder placed after the deadline (TSK-5.4, D-24) | "{task}: {n}m placed after the deadline" |
| `TASK_DEFERRED` | placement | deferred beyond window (info, no flag) | — |
| `TASK_ATOMIC_NO_FIT` | flag | atomic task has no contiguous slot | "{task} needs {n}m in one piece" |
| `PRECLEAN_SOURCE_CLOSED` | release | block of a done/skipped/deleted/deferred item removed | "{title} removed — {reason}" |
| `PRECLEAN_ORPHAN` | release | app-owned Google event with no placement (IN-05); always **ask** | "Remove stray event {title}?" |
| `CALENDAR_UNROUTED` | flag | (service-level, BE-13) block has no writable calendar | "{kind} has no calendar — choose one in Settings" |
| `PRECLEAN_NO_LONGER_FITS` | placement | existing engine block not reproduced | "{title} no longer fits" |
| `FREED_REFILLED_FLAGGED_FIRST` | release | a previously flagged task got placed into freed time | "{task} took the freed {time}" |

`Category` values: `shrink, held, prayer, release, placement, flag, pin, sync, apply, system`.

---

## 4. Types (`types.py`)

All dataclasses are `@dataclass(frozen=True, slots=True)` unless they are mutable work state.
UUIDs are `uuid.UUID`. Datetimes are tz-aware.

```python
# ---------- settings projection (built by the service from AppSettings) ----------
@dataclass(frozen=True)
class DayFrameRule:
    weekday: int                         # 1..7
    office: tuple[time, time] | None
    earliest_block: time
    latest_block_end: time

@dataclass(frozen=True)
class PrayerRule:
    name: str                            # fajr|dhuhr|jummah|asr|maghrib|isha
    enabled: bool
    duration_min: int
    edge_min: int

@dataclass(frozen=True)
class EngineSettings:
    tz: ZoneInfo
    precedence: tuple[str, ...]          # 7 keys
    planning_window_days: int
    slot_granularity_min: int
    min_chunk_min: int
    max_chunk_min: int
    buffers_by_effort: Mapping[str, int] # effort_key -> minutes
    office_allowed_by_effort: Mapping[str, bool]
    placement_order: str                 # earliest_first|deadline_first
    day_rules: Mapping[int, DayFrameRule]
    prayer_rules: Mapping[str, PrayerRule]
    qada_cap_per_day: int
    qada_gap_min: int
    meeting_gap_min: int
    jummah_overrides_dhuhr: bool
    auto_apply_safe: bool
    auto_apply_creates: str              # when_safe|never (D-14)
    safe_create_lead_min: int
    ask_before_cross_day_moves: bool

# ---------- input ----------
@dataclass(frozen=True)
class DayOverride:
    date: date
    earliest_block: time | None
    latest_block_end: time | None

@dataclass(frozen=True)
class Meeting:
    id: str                              # external_event.id
    start: datetime; end: datetime
    summary: str

@dataclass(frozen=True)
class PrayerDay:                          # one prayer_instance's inputs (service computes times)
    instance_id: UUID
    date: date
    name: str
    anchor: datetime                     # preferred start
    window_start: datetime
    window_end: datetime
    state: str                           # normal|shifted|qada|prayed (current DB state)
    prayed_at: datetime | None
    drift_flag: bool
    drift_min: int | None

@dataclass(frozen=True)
class FixedBlock:                         # pinned or frozen existing placement
    placement_id: UUID
    kind: str                            # pinned|frozen
    ref_type: str                        # task|habit|prayer
    ref_id: UUID
    block_kind: str                      # task_chunk|habit|prayer|qada
    start: datetime; end: datetime
    effort_key: str | None               # for buffer after task chunks
    title: str

@dataclass(frozen=True)
class OccurrenceIn:
    date: date
    state: str                           # scheduled|done|skipped|missed
    occurrence_id: UUID | None

@dataclass(frozen=True)
class HabitIn:
    id: UUID
    name: str
    weekdays: frozenset[int]
    ideal_min: int
    min_min: int
    not_before: time
    not_after: time
    ideal_time: time | None
    priority_rank: int                   # higher = more important
    compressible: bool                   # already False when min==ideal
    active_from: date
    state: str                           # active|ended|archived  (non-active → no occurrences)
    occurrences: Mapping[date, OccurrenceIn]

@dataclass(frozen=True)
class TaskIn:
    id: UUID
    title: str
    state: str
    remaining_min: int | None            # None if est missing
    priority_rank: int | None            # None if missing
    has_calendar: bool
    deadline: datetime | None
    effort_key: str
    split_behaviour: str                 # atomic|subtasks|auto
    unit_minutes: tuple[int, ...]        # remaining undone subtask weights (subtasks mode)
    min_chunk_min: int | None            # per-task override
    deferred_until: date | None
    depends_on: tuple[UUID, ...]
    done_dependency_ids: frozenset[UUID] # deps that are done
    previously_flagged: bool
    created_at: datetime
    archived: bool

@dataclass(frozen=True)
class CurrentBlock:                       # active engine-owned, NON-pinned, start >= now
    placement_id: UUID
    ref_type: str; ref_id: UUID          # for habits ref_id = occurrence id; see group_key
    group_key: str                       # see §8.1
    block_kind: str
    start: datetime; end: datetime
    calendar_hint: str | None
    title: str

@dataclass(frozen=True)
class PlanInput:
    now: datetime
    settings: EngineSettings
    day_overrides: tuple[DayOverride, ...]
    meetings: tuple[Meeting, ...]
    prayers: tuple[PrayerDay, ...]
    fixed: tuple[FixedBlock, ...]        # pinned + frozen
    habits: tuple[HabitIn, ...]
    tasks: tuple[TaskIn, ...]
    hints: tuple[CurrentBlock, ...]      # previous engine placements (D-10)
    released: tuple[Interval, ...] = ()  # time the user just freed (D-14 rule 6), from the replan job payload

# ---------- output ----------
@dataclass(frozen=True)
class PlannedBlock:
    group_key: str                       # §8.1
    block_kind: str                      # prayer|qada|habit|task_chunk
    ref_type: str                        # prayer|habit|task
    ref_id: UUID                         # prayer_instance id | habit id | task id
    occurrence_date: date | None         # habits
    start: datetime; end: datetime
    title: str
    rule: RuleCode
    why: tuple[str, ...]                 # bullets for the detail drawer
    meta: Mapping[str, Any]              # chunk_index, chunk_count, compressed_from, qada_index…

@dataclass(frozen=True)
class Flag:
    code: RuleCode
    subject_type: str                    # task|habit|prayer|placement
    subject_id: UUID
    title: str
    detail: str
    needed_min: int | None = None
    placed_min: int | None = None
    available_before_shrink_min: int | None = None
    shrink_gained_min: int | None = None
    short_min: int | None = None
    deadline: datetime | None = None
    levers: tuple[str, ...] = ()         # push_deadline|skip_habit|make_time|reduce_task
    blocked_by: tuple[UUID, ...] = ()    # dependency chain or pinned placement ids

@dataclass(frozen=True)
class LogEntry:
    rule: RuleCode
    subject_type: str; subject_id: UUID
    title: str; detail: str
    effect: Mapping[str, Any]

@dataclass(frozen=True)
class TaskResult:
    task_id: UUID
    status: str                          # placed|partial|unplaced|blocked|skipped_state|deferred
    placed_min: int
    short_min: int

@dataclass(frozen=True)
class HabitResult:
    habit_id: UUID
    date: date
    planned_min: int | None              # None = not placed
    compressed_min: int                  # ideal - planned (fit or shrink), 0 if none

@dataclass(frozen=True)
class PrayerResult:
    instance_id: UUID
    state: str                           # normal|shifted|qada|prayed
    start: datetime; end: datetime
    qada_index: int | None

@dataclass(frozen=True)
class PlanOutput:
    blocks: tuple[PlannedBlock, ...]     # sorted by (start, group_key)
    flags: tuple[Flag, ...]              # sorted by (code, subject_id)
    log: tuple[LogEntry, ...]
    tasks: tuple[TaskResult, ...]
    habits: tuple[HabitResult, ...]
    prayers: tuple[PrayerResult, ...]
```

---

## 5. Time primitives

### 5.1 `Interval`
```python
@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime                        # half-open [start, end)
    def minutes(self) -> int
    def overlaps(self, o) -> bool        # self.start < o.end and o.start < self.end
    def contains(self, o) -> bool
    def intersect(self, o) -> Interval | None
```

### 5.2 `IntervalSet` — sorted, non-overlapping, merged
Methods: `add(iv)`, `subtract(iv)`, `subtract_set(s)`, `intersect(iv)`, `iter()` (chronological),
`total_minutes()`. Implement with a plain sorted list + merge; n is small (< 500).
**Unit tests:** merge adjacency (`[1,2)+[2,3) → [1,3)`), subtract inner/edge/outer, empty
results, intersect.

### 5.3 `Occupancy`
Holds every placed block with its **blocking interval**:

```python
@dataclass
class Occupied:
    interval: Interval                   # the block itself
    buffer_after_min: int                # FR-4, only task chunks (pinned/frozen task chunks too)
    kind: str                            # meeting|prayer|qada|pinned|frozen|habit|task_chunk
    rank_key: str                        # precedence key it was placed under
    ref: tuple[str, UUID]                # (ref_type, ref_id)
    title: str

class Occupancy:
    def add(self, occ: Occupied) -> None
    def remove(self, ref, interval) -> None        # used by shrink
    def blocked(self) -> IntervalSet                # union of [start, end + buffer_after)
    def overlapping(self, iv: Interval) -> list[Occupied]
    def next_start_after(self, t) -> datetime | None
```

### 5.4 Rounding (`timeutil.py`)
- `ceil_to_grid(dt, g, tz)` / `floor_to_grid(...)`: align **local** wall-clock minutes to
  multiples of `g` (local midnight = 0).
- `local_dt(d: date, t: time, tz) -> datetime`, `local_date(dt, tz) -> date`.
- `daterange(d0, d1)` inclusive.

---

## 6. The algorithm

### 6.1 Frames (`frames.py`)

```
window_days = [today + i for i in range(planning_window_days)]   # today = local_date(now)
for d in window_days:
    rule = day_rules[d.isoweekday()]
    ov = day_overrides.get(d)
    frame_start = local_dt(d, ov.earliest_block or rule.earliest_block)
    frame_end   = local_dt(d, ov.latest_block_end or rule.latest_block_end)   # if ≤ start, +1 day
    office[d]   = Interval(local_dt(d, rule.office[0]), local_dt(d, rule.office[1])) if rule.office else None
window_start = now_ceil
window_end   = frame_end(last day)
```

`task_allowed(d, effort_key)` = `IntervalSet([frame(d)]) ∩ [now_ceil, ∞)` minus `office[d]` **if**
the office gate is active for tasks (D-16) **and** `office_allowed_by_effort[effort_key]` is
false.

### 6.2 Fixed blocks first: frozen
Frozen blocks (engine placements that started before `now`) are history. Add each to the
occupancy **before any phase**, with `rank_key="frozen"` and buffer per effort if a task chunk.
They are never output, never diffed.

### 6.3 Prayers (`prayers.py`) — phase `prayers`

Input `PrayerDay` rows are already filtered by the service: Jummah replaces Dhuhr on Fridays when
`jummah_overrides_dhuhr` (the service simply does not send Dhuhr that day). Disabled prayers are not sent.

For each **date** ascending, process that date's prayers in canonical order
`fajr, dhuhr|jummah, asr, maghrib, isha`:

```
# Pre-checks — in this order, first hit wins:
if a frozen or pinned FixedBlock exists with ref ('prayer', instance_id):
    continue                 # already running/past, or user-moved: it is in occupancy already;
                             # but remember it as "this day's Isha" if name == isha (for qada)
if state == 'prayed':
    continue                 # PRY-6: no block. The service already truncated the placement
                             # (BE-12) and the frozen/pinned part, if any, is in occupancy.
                             # Any remaining engine block for it is deleted by the diff with
                             # reason PRECLEAN_SOURCE_CLOSED (safe).
if window_end <= now_ceil:
    continue                 # the whole window is in the past and nothing was placed: emit nothing

obstacles = occupancy.blocked()     # contains meetings iff meetings rank above prayers,
                                    # plus frozen & anything else ranked above
d = duration_min
pref = Interval(anchor, anchor + d)
# every candidate start below must also satisfy s >= now_ceil

if pref.start >= now_ceil and pref does not overlap obstacles:
    place pref → rule PRAYER_PLACED, state normal          # D-06
else:
    core = Interval(window_start + edge, window_end - edge)
    # gap(o) = meeting_gap_min if o.kind == 'meeting' else 0     (D-07; uses Occupied.kind)
    candidates = []
    for each Occupied o overlapping core ∪ pref, sorted by (start, kind):
        candidates.append(ceil_to_grid(o.interval.end + gap(o)))          # start right after
        candidates.append(floor_to_grid(o.interval.start - gap(o) - d))   # end right before
    candidates += [core.start, core.end - d, now_ceil]
    valid = [s for s in candidates
             if s >= now_ceil
             and core.contains(Interval(s, s+d))
             and Interval(s, s+d) overlaps no Occupied
             and no Occupied o with kind == 'meeting' and o.end in (s - gap, s]
             and no Occupied o with kind == 'meeting' and o.start in [s+d, s+d+gap)]
    if valid: choose min by (abs(s - anchor), s)          # closest to preferred, then earlier
              → rule PRAYER_SHIFTED, state shifted
    else:     → mark for qada
```

**Qada stacking (after all of the day's non-qada prayers are placed):**
```
isha = today's isha block (placed now, or frozen/pinned), else None
cursor = max((isha.end if isha else isha_window_end) + qada_gap_min, now_ceil)
limit  = local midnight at the end of that date (next day 00:00)
qadas = prayers marked for qada, in canonical order
for i, p in enumerate(qadas, start=1):
    if i > qada_cap_per_day: flag PRAYER_QADA_CAP (subject = that prayer), stop
    s = earliest t ≥ cursor, on grid, with Interval(t, t+d) free of obstacles (meetings may exist late at night)
    if s is None or s + d > limit: flag PRAYER_QADA_NO_ROOM (subject = that prayer); continue
    place → block_kind 'qada', rule PRAYER_QADA (i==1) or PRAYER_QADA_STACKED (i>1), meta.qada_index=i
    cursor = s + d + qada_gap_min
```
A qada is **never** placed before Isha (PRY-4). Qada placements are ordinary occupancy for
everything ranked below prayers, so no task or habit can take them (PRY-5, FR-7.2).

If `drift_flag`: place normally but add `Flag(PRAYER_DRIFT)` and mark the block's meta
`{"drift": true}` so classification makes its changes **ask** (D-14).

**Acceptance checks for this phase (write as tests):**
- **A1:** window 13:00–14:00, d=30, edge=10, gap=5, meeting 13:00–13:15 → 13:20–13:50, state shifted.
- No meeting → 13:00–13:30, state normal.
- Meeting 13:00–13:45 → candidates: 13:50 (exceeds core end 13:50−30) invalid; → qada.
- Two qadas same day → stacked back-to-back after Isha end, indexes 1 and 2.
- Isha itself blocked → its qada starts at isha window_end (+gap).
- Prayed prayer → engine emits no block for it (truncation is BE-12's job); its old engine block is deleted with `PRECLEAN_SOURCE_CLOSED` (safe).
- Run at 14:00 → today's Fajr/Dhuhr (windows passed, nothing placed) produce no block; no invariant error.
- Frozen (running) Asr → no second Asr block.
- Run at 22:00 with a pending qada → qada starts ≥ 22:00 (never in the past).

### 6.4 Meetings & pinned — phases `meetings`, `pinned`

```
place_fixed(blocks, rank_key, conflict_code):
    for b in sorted(blocks, key=(start, id)):
        clash = occupancy.overlapping(b.interval)          # only things already placed = higher ranks
        if clash: flags.append(Flag(conflict_code, …, blocked_by=[c.ref ids]))
        occupancy.add(b, rank_key)                         # still occupies time below
        if rank_key == 'pinned': log PINNED_LEFT_ALONE (once per block per run)
```
Meetings use `MEETING_CONFLICT`, pinned use `PINNED_CONFLICT`. With the default order there are
never meeting conflicts (meetings are placed first).
**D-15 amendment:** when placing **pinned** blocks, overlaps with `kind == 'meeting'` are **not**
conflicts (no flag); only overlaps with prayer/qada (or anything else ranked above pinned that
is not a meeting) raise `PINNED_CONFLICT`. The pinned block and the meeting both stay in
occupancy.

### 6.5 Habits (`habits.py`) — phase `habits`

```
occurrences = []
for h in habits where h.state == 'active':
    for d in window_days where d.isoweekday() in h.weekdays and d >= h.active_from:
        occ = h.occurrences.get(d)
        if occ and occ.state in ('done','skipped','missed'): 
            if occ.state == 'skipped': (diff will emit release for any existing block)
            continue
        if a frozen OR pinned block exists for (habit h, date d): continue   # already running/past or user-moved
        occurrences.append((d, h))
sort occurrences by (d, -h.priority_rank, h.ideal_time or h.not_before, h.name, h.id)

for (d, h) in occurrences:
    ideal = ceil_to_grid_minutes(h.ideal_min); minimum = ceil_to_grid_minutes(h.min_min)   # D-26
    W = Interval(local_dt(d, h.not_before), local_dt(d, h.not_after)) ∩ [now_ceil, ∞)
    if W empty: continue                                   # window already passed today
    free = IntervalSet([W]).subtract_set(occupancy.blocked())
    target = local_dt(d, h.ideal_time or h.not_before)
    s = best_start(free, h.ideal_min, target)              # nearest to target, tie → earlier
    if s: place(h, d, s, h.ideal_min, rule = HABIT_PLACED if s == target else HABIT_MOVED)
    elif h.compressible:
        iv = longest interval in free (tie → closest to target)
        L = floor_to_grid_len(iv.minutes)
        if L >= h.min_min:
            length = min(L, h.ideal_min)
            s = best_start(IntervalSet([iv]), length, target)
            place(h, d, s, length, rule=HABIT_FIT_COMPRESSED, compressed_min = ideal − length)
        else: flag HABIT_NO_ROOM
    else: flag HABIT_NO_ROOM

best_start(free, length, target):
    for each iv in free with iv.minutes >= length:
        lo = ceil_to_grid(iv.start); hi = floor_to_grid(iv.end - length)
        if lo > hi: continue
        cand = clamp(round_to_grid(target), lo, hi)
    return candidate minimising (abs(cand - target), cand)
```

Habits have no effort → `buffer_after_min = 0`. Habits are **not** gated by office hours.

### 6.6 Task eligibility & order (`ordering.py`)

For each task, in this order of checks (first hit wins → `TaskResult.status`):

| Check | Result | Flag code |
|---|---|---|
| `archived` or state in (`done`,`skipped`,`backlog`) | `skipped_state` | — |
| `remaining_min is None` or `priority_rank is None` | `blocked` | `TASK_BLOCKED_MISSING_FIELDS` (detail lists "estimate"/"priority") |
| `not has_calendar` | `blocked` | `TASK_BLOCKED_NO_CALENDAR` |
| `remaining_min <= 0` | `skipped_state` | — |
| `deferred_until` > last window day | `deferred` | — (log `TASK_DEFERRED`) |

Eligible tasks are sorted by:
```
key = (0 if t.previously_flagged else 1,          # PRY-6 / TSK-5.3 "flagged first"
       t.deadline or MAX_DT,
       -t.priority_rank,
       t.created_at,
       t.id)
```
Then a **stable topological sort** (Kahn's algorithm, picking the smallest `key` among ready
nodes) ensures every dependency is processed before its dependents. Cycles (should be
prevented on write) → all tasks in the cycle are `blocked` with `TASK_BLOCKED_DEPENDENCY`.

### 6.7 Chunking (`chunking.py`)

```python
def next_chunk(N: int, L: int, *, m: int, M: int, g: int, behaviour: str,
               units: list[int]) -> int | None:
    """N = minutes still needed, L = usable contiguous minutes in this slot (already minus the
    chunk's own buffer). Returns minutes to place here, or None to skip this slot."""
```

- `L = floor(L / g) * g`.
- **atomic:** return `N if L >= N else None`.
- **auto:**
  ```
  if N <= m:            return N if L >= N else None        # whole small task or the m-rounded remainder (D-25)
  cap = min(L, M, N)
  if cap < m:           return None
  if cap == N:          return N
  rest = N - cap
  if rest < m:                                              # avoid an orphan < m
      alt = N - m
      return alt if alt >= m else None
  return cap
  ```
- **subtasks:** `units` = remaining undone subtask minutes in order, **pre-merged** by
  `merge_units(units, m)`: walk left→right accumulating until the accumulator ≥ m, emit it;
  a trailing remainder < m is merged into the previous emitted unit (or becomes the only unit
  if nothing was emitted). Then: take the longest prefix of merged units whose sum ≤ min(L, M);
  if even the first unit > min(L, M): return `units[0]` if `L >= units[0]` else `None` (a unit
  bigger than M is still placed whole). After placing, pop the consumed units.

**Unit tests (table-driven):** 
| N | L | m | M | behaviour | units | expect |
|---|---|---|---|---|---|---|
| 120 | 300 | 30 | 180 | auto | – | 120 |
| 120 | 100 | 30 | 180 | auto | – | 90 (rest 30 ok → cap 100→ floor grid 100; rest 20<30 → alt 90) |
| 45 | 40 | 30 | 180 | auto | – | None (alt 15 < 30) |
| 20 | 25 | 30 | 180 | auto | – | 20 |
| 210 | 60 | 30 | 180 | auto | – | 60 |
| 105 | 200 | 30 | 180 | atomic | – | 105 |
| 105 | 100 | 30 | 180 | atomic | – | None |
| 120 | 75 | 30 | 180 | subtasks | [30,30,45,15] → merged [30,30,60] | 60 |

### 6.8 Task slot search (`tasks.py`) — phase `tasks`

```
for t in ordered_tasks:
    need = t.remaining_min
           - minutes of frozen chunks of t whose end > now (count only now→end)
           - minutes of pinned chunks of t that start ≥ now (a pinned chunk is planned work, A9)
    need = ceil_to_grid_minutes(need)     # D-26: engine works in whole grid steps
    if need <= 0: status placed; continue
    m = t.min_chunk_min or settings.min_chunk_min
    buf = buffers_by_effort.get(t.effort_key, 0)

    # dependency gate (D-13)
    ready_at = now_ceil
    for dep in t.depends_on:
        if dep in t.done_dependency_ids: continue
        r = results[dep]
        if r is None or r.status != 'placed' (fully): blocked TASK_BLOCKED_DEPENDENCY (blocked_by = chain); next task
        ready_at = max(ready_at, last_chunk_end(dep) + buffer(dep))   # chunks incl. pinned & frozen ones
    earliest = max(ready_at, start_of_day(t.deferred_until) if t.deferred_until else ready_at)
    latest   = min(t.deadline or window_end, window_end)
    if earliest >= latest: → unplaced (flag TASK_NO_SLOT, detail "deadline already passed" if deadline < now)

    placed = []
    # 1. hints (D-10) — previous engine chunks of this task, chronological
    for h in hints of t:
        iv = Interval(h.start, h.end) clipped so that length <= need
        if valid_slot(iv, t) and next_chunk(need, iv.minutes, …) == iv.minutes:
            place(iv, rule TASK_KEPT_SLOT); need -= iv.minutes
    # 2. search
    days = daterange(local_date(earliest), local_date(latest))
    if placement_order == 'deadline_first': days = reversed(days)
    for d in days:
        free = task_allowed(d, t.effort_key) ∩ [earliest, latest] − occupancy.blocked()
        intervals = free.iter() (reversed if deadline_first)
        for iv in intervals:
            while need > 0:
                usable = usable_minutes(iv, buf)     # see below
                c = next_chunk(need, usable, …)
                if c is None: break
                s = iv.start (earliest_first)
                    or floor_to_grid(iv.end - (buf if iv ends at an occupied block else 0) - c) (deadline_first)
                place(Interval(s, s+c)) ; need -= c
                iv = remaining part of iv after the placed chunk + its buffer
        if need == 0: break
    # 3. shrink (only with a deadline)
    if need > 0 and t.deadline: need = shrink_for(t, need, earliest, latest)   # §6.9
    # 4. result
    if t.split_behaviour == 'atomic' and need > 0:
        remove all chunks placed for t in this run; flag TASK_ATOMIC_NO_FIT (short = full)
    elif need > 0:
        flag TASK_PARTIAL_FLAGGED if placed else TASK_NO_SLOT (or TASK_BLOCKED_PINNED, see below)
        short = need                                 # flag keeps the before-deadline shortfall
        # 5. overflow (TSK-5 step 4, D-24): place the remainder in later free time, after the
        #    deadline, inside the window. These chunks carry meta.overflow=true and the flag stays.
        if t.deadline and t.deadline < window_end:
            repeat step 2 with earliest = t.deadline, latest = window_end, rule TASK_OVERFLOW
```

**`usable_minutes(iv, buf)`**: if another occupied block starts exactly at `iv.end` (i.e. the
interval ends because something is there), the chunk needs its buffer inside the interval:
`iv.minutes - buf`. If the interval ends because the day frame / deadline / office window
ends, the buffer may spill past it: `iv.minutes`.

**`valid_slot(iv, t)`**: `iv` ⊆ `task_allowed(day, effort)` ∩ `[earliest, latest]`, `iv` and
`[iv.end, iv.end+buf)` don't overlap `occupancy.blocked()`, and start/end on grid.

**`TASK_BLOCKED_PINNED`**: when `need > 0` and nothing was placed, check whether removing pinned
blocks from the obstacles would have allowed placement (one what-if pass inside the engine,
pinned-only). If yes, flag with `blocked_by` = those pinned placement ids. Otherwise `TASK_NO_SLOT`.

**Chunk meta:** after a task is done, number its chunks chronologically:
`meta.chunk_index` (1-based) and `meta.chunk_count`.

**Flag detail numbers** (OVL-1, spec §8 "3h 30m needed · 1h 00m available · 30m short after max shrink"):
`needed_min = need at start`, `available_before_shrink_min = placed before shrink`,
`shrink_gained_min`, `short_min = need left`. Levers: `push_deadline` if deadline;
`skip_habit` if any non-frozen habit occurrence lies between earliest and latest;
`make_time` always (days in range); `reduce_task` if the task has undone subtasks.

### 6.9 Minimal shrink (`shrink.py`) — HAB-3, ENG-1 step 3, D-11

```
def shrink_for(t, need, earliest, latest) -> int:
    candidates = [hb for hb in placed habit blocks in this run
                  if hb.habit.compressible
                  and hb.length > hb.habit.min_min
                  and earliest <= hb.start and hb.end <= latest]
    sort by (hb.habit.priority_rank asc,    # least important habit first
             -hb.start.timestamp(),         # closest to the deadline first
             hb.habit.id)
    for hb in candidates:
        if need == 0: break
        flex = hb.length - hb.habit.min_min
        best = None
        for side in ('tail', 'head'):
            c_max = chunk_if_shrunk(t, hb, side, flex, need)   # simulate on a copy
            if c_max is None: continue
            # smallest k (grid steps) that still yields c_max
            k = min(k for k in range(g, flex + g, g) if chunk_if_shrunk(t, hb, side, k, need) == c_max)
            cand = (c_max, -k, side == 'tail')                 # bigger chunk, smaller shrink, prefer tail
            best = max(best, (cand, side, k)) 
        if best is None: continue
        apply: shorten hb by k on `side`; place the chunk adjacent to the freed side;
               set the habit block's meta `shrunk_for_task_id = t.id` (used by D-14 classification)
        log HABIT_SHRUNK_FOR_TASK  effect {gave_min: k, wanted_min: need_before, floor_min: min_min}
        if hb.length == min_min: log HABIT_HELD_AT_FLOOR
        need -= c_max
    if need > 0:
        # separate scan: hard (non-compressible) habit blocks inside [earliest, latest] that
        # touch a free interval usable by this task (block end == free start or vice versa)
        for each such hard habit block: log HABIT_HARD_NOT_COMPRESSED (HAB-2: never asks to override)
    return need

chunk_if_shrunk(t, hb, side, k, need):
    tmp = occupancy copy; replace hb by its shortened interval
    freed point p = hb.end - k (tail) or hb.start + k (head)
    iv = the free interval of task_allowed(d, effort) ∩ [earliest, latest] − tmp.blocked() that contains p (tail) / ends at p (head)
    return next_chunk(need, usable_minutes(iv, buf), …)
```

Shrinking is done **only here**, after normal search failed (ENG-1 "never the first move").
Shrunk habits get `HabitResult.compressed_min = ideal − new_length` and the block's
`meta.compressed_from = ideal`.

**Acceptance (tests):**
- **A3:** only slot is inside a 3h habit (min 60), task 45m Low, deadline that evening → habit
  becomes 2h 15m (tail shrink 45), log effect `gave_min=45`.
- **A4:** task 3h 30m, 1h free elsewhere, habit 3h (min 60) → 1h placed by search, 2h by shrink,
  habit at 60m, flag `TASK_PARTIAL_FLAGGED` with `short_min=30`, `available_before_shrink_min=60`,
  `shrink_gained_min=120`.
- Hard habit only blocker → task flagged, habit untouched, `HABIT_HARD_NOT_COMPRESSED` logged.

### 6.10 Flags & overload (`flags.py`)
Collect flags from every phase. One flag per (code, subject). Sort by (code, subject_id). The
engine **never** chooses a lever (OVL-2). Lever *consequences* are computed by the service via
what-if (§10).

### 6.11 Orchestration (`planner.py`)

```python
def plan(inp: PlanInput) -> PlanOutput:
    st = State(inp)                         # occupancy, frames, results, flags, log
    place_frozen(st)                        # §6.2
    office_gate_for = set(ranks after 'office_hours' in precedence)  # D-16
    for key in inp.settings.precedence:
        {"meetings": place_meetings, "prayers": place_prayers,
         "office_hours": lambda st: None,  # constraint only
         "pinned": place_pinned, "habits": place_habits,
         "tasks": place_tasks, "backlog": lambda st: None}[key](st)
    out = st.build_output()                 # sort everything
    invariants.check(out, inp)              # §7, raises on bug
    return out
```

The office gate applies to tasks only when `office_hours` precedes `tasks` in the order (default).

### 6.12 "Why it landed here" bullets (`why.py`)
For each task chunk, add bullets only when the condition was relevant (mockup web/06 right panel):
- effort gate active on that day → `"High effort → never inside office hours {10:00–18:30}"`
- a prayer/qada block is the immediately previous or next occupied block of the chunk on that day → `"Prayers are hard blocks → {Asr 15:35, Isha 19:45}"`
- chunk_count > 1 → `"Min chunk {30}m → {2h} split into {4} units"` (auto) or `"{n} subtasks"`.
- buf > 0 → `"Buffer {15}m after {High} work"`
- deadline → `"Deadline {Thu 23:59}"`
- dependency → `"Depends on {W2D2} → after {Wed 20:30}"`
- rule TASK_KEPT_SLOT → `"Kept its previous slot"`
Times formatted in local tz, `HH:MM`, days as `Mon 24`.

---

## 7. Invariants (`invariants.py`)

`check(out, inp)` raises `EngineInvariantError(code, detail)` if any fails:
1. **No double-booking** among `out.blocks` ∪ frozen ∪ meetings-ranked-above? → precisely: no two
   output blocks overlap; no output block overlaps a frozen block; no task chunk overlaps a
   meeting, prayer or qada (FR-7.1, PRY-7, FR-7.2). (Pinned overlaps are allowed only for blocks
   ranked **above** pinned — D-15.)
2. No task chunk shorter than its `m`, except a task whose **total estimate** is < m, which is
   placed whole (D-25).
3. No task chunk of an effort with `office_allowed=false` intersects an office interval while the gate is active.
4. Every task chunk ends ≤ its task's deadline, **except** chunks with `meta.overflow=true` (D-24), which must start ≥ the deadline.
5. Every habit block length ∈ [min_min, ideal_min].
6. No qada block starts before that day's Isha block end (or Isha window end).
7. All task-chunk and habit starts/ends are on the grid. (Prayers keep their configured anchors, e.g. 15:35, even if the grid changes; qada starts follow Isha's end.)
8. Every eligible task appears in `out.tasks` exactly once (G1: nothing silently dropped).
9. No block starts before `now_ceil`.

---

## 8. Diff (`diff.py`)

### 8.1 Group keys
| Block | group_key |
|---|---|
| task chunk | `task:{task_id}` |
| habit | `habit:{habit_id}:{YYYY-MM-DD}` |
| prayer / qada | `prayer:{YYYY-MM-DD}:{name}` |

### 8.2 Algorithm
```
current = CurrentBlocks (active, engine-owned, not pinned, start >= now)
planned = out.blocks
for each group_key in sorted(union of keys):
    C = sorted(current[g], key=start); P = sorted(planned[g], key=start)
    # 1. exact matches → no change
    remove pairs with identical (start, end)
    # 2. pair the rest in order
    for c, p in zip(C, P):
        same_day = local_date(c.start) == local_date(p.start)
        if c.start == p.start or c.end == p.end: kind = 'resize'
        else: kind = 'move'
        emit Change(kind, from=c, to=p, cross_day = not same_day)
    # 3. leftovers
    for p in P[len(C):]: emit Change('create', to=p)
    for c in C[len(P):]: emit Change('delete', from=c, reason=delete_reason(c))
```
`delete_reason(c)`: `PRECLEAN_SOURCE_CLOSED` if the source task is done/skipped/backlog/archived,
or deferred past the block's date, or the habit occurrence is skipped/done, or the habit is
ended/archived, or the prayer instance is `prayed`; else `PRECLEAN_NO_LONGER_FITS`. Orphans
from `calendar_orphan` (IN-05) are added by the service as `delete` changes with
`PRECLEAN_ORPHAN` (ask).

### 8.3 Change shape (stored in `plan_run.changes`, sent to the UI)
```json
{
  "id": "c_3f9a1b2c4d5e",              // sha1(kind|group_key|from|to)[:12]
  "kind": "move",                      // create|move|resize|delete
  "group_key": "task:…",
  "ref_type": "task", "ref_id": "…", "placement_id": "…|null",
  "block_kind": "task_chunk",
  "title": "Inbox triage",
  "from": {"start": "…", "end": "…"} , "to": {"start": "…", "end": "…"},
  "cross_day": false,
  "delta_min": -65,                    // to.start - from.start, or length delta for resize
  "rule": "TASK_PLACED",
  "reason": "Dhuhr occupies 13:00–13:30; 20m gap after LR1 ends. Low effort fits anywhere.",
  "why": ["…"],
  "classification": "safe",            // safe|ask
  "requires": ["c_…"],                 // must be accepted together (§8.5)
  "meta": {"chunk_index": 1, "chunk_count": 4}
}
```
`reason` = the first `why` bullet joined with the rule title. Keep it to one line (RPL-2).

### 8.4 Classification (`classify.py`, D-14)

| Change | Class |
|---|---|
| create inside `input.released` (whole block within one released interval) | `safe` if `requires == []` and no shrink for its task — even if the task is flagged and even inside the lead time (D-14 rule 6) |
| create | `safe` only if `auto_apply_creates == "when_safe"` **and** all D-14 conditions hold: `requires == []`; no block in this output has `meta.shrunk_for_task_id == this task`; task not flagged in this run and block not `meta.overflow`; `start ≥ now + safe_create_lead_min`. Else `ask`. (Classification runs after `requires` is computed.) |
| move, same day | `safe` |
| move, cross day | `ask` (always — RPL-3; `ask_before_cross_day_moves=false` may set `safe`) |
| resize, habit | `safe` |
| resize, task chunk | `ask` |
| resize/move, prayer or qada, same day | `safe`, unless block meta `drift` → `ask` |
| delete, `PRECLEAN_SOURCE_CLOSED` | `safe` |
| delete, `PRECLEAN_ORPHAN` | `ask` (always) |
| delete, other | `ask` |
| anything on a pinned block | not emitted (pinned never appear in `current`) |

### 8.5 `requires`
For every pair (X, Y): X requires Y if `X.to` overlaps `Y.from` (X needs the space Y vacates).
Take the transitive closure. The UI auto-checks required changes when the user ticks one, and
`apply` rejects a selection that breaks closure (409 `CONFLICT_REQUIRES`).

### 8.6 Idempotence (ENG-4)
If the current placements equal the last applied output and nothing else changed, `diff` is
empty. Test: `out1 = plan(inp)`; materialise `out1.blocks` as `CurrentBlock`s and as `hints`;
`out2 = plan(inp')`; `diff(...) == []`.

---

## 9. Performance (NFR-7: plan run < 2 s)
14 days × (≈ 6 prayers + ≈ 6 habits + ≈ 10 chunks) ≈ 300 blocks. Interval ops are O(n). The
shrink scan is bounded by `flex/g` steps × candidates. Add a benchmark test with 60 tasks, 8
habits, 30 meetings: `plan()` must finish in < 500 ms on CI.

---

## 10. What-if (`whatif.py`)

```python
def what_if(base_inp: PlanInput, base_out: PlanOutput, mutate: Callable[[PlanInput], PlanInput]) -> WhatIfResult
```
```python
@dataclass(frozen=True)
class TaskGain:
    task_id: UUID; title: str
    placed_min_before: int; placed_min_after: int
    first_new_chunk_start: datetime | None
@dataclass(frozen=True)
class WhatIfResult:
    gains: tuple[TaskGain, ...]            # tasks whose placed_min changed, sorted by gain desc
    flags_cleared: tuple[Flag, ...]
    flags_added: tuple[Flag, ...]
    freed: tuple[Interval, ...]            # intervals occupied before and free after
    summary: str                           # "frees 18:30 → W2D2 can start today"
```
Returns per-task `placed_min` deltas, flags cleared/added, and the **earliest newly placed
chunk** per task. Used by:
- **Skip preview (HAB-12, UX-6):** mutate the occurrence to skipped → "frees 18:30 → W2D2 can start today".
- **Skip-until preview (HAB-8a):** service-side only (streak math), plus a what-if for freed time.
- **Overload levers (OVL-2):** one what-if per lever candidate (≤ 6 runs) → "fits · uses the
  office→evening gap, keeps Gym at 60m".
- **Precedence preview (SET-5):** mutate settings.precedence → summary of changes for this week.

---

## 11. Engine work packages

> Write tests in `backend/tests/engine/`. Use the builders in `tests/fixtures/engine_builders.py`
> (EN-02) so tests read like the acceptance scenarios: `day("2026-11-27").meeting("13:00","13:15")`.

### EN-01 — Types, rule codes, enums
**Depends on:** F-02 **Size:** S
**Files:** `engine/types.py`, `engine/rules.py`, `engine/__init__.py` (exports `plan`, `diff`, types)
**Steps:** transcribe §3 and §4 exactly. Add `EngineInvariantError`. Constructors assert tz-aware datetimes.
Create `invariants.py` with a stub `def check(out, inp) -> None: pass` (filled in by EN-12) so
the planner can call it from day one.
**Tests:** `test_types.py` — naive datetime raises; every `RuleCode` has a category and title template.
**Done when:** `mypy --strict` passes on `engine/`.

### EN-02 — Time primitives & test builders
**Depends on:** EN-01, DB-02 (builders import the default values from `seed/defaults.py`) **Size:** M
**Files:** `engine/timeutil.py`, `engine/occupancy.py`, `tests/fixtures/engine_builders.py`
**Steps:** implement §5. Builders: `settings(**overrides)` returning default `EngineSettings`
(values identical to `seed/defaults.py`), `at("2026-11-27 13:00")` → IST datetime,
`InputBuilder` with fluent `.meeting()`, `.prayer()`, `.habit()`, `.task()`, `.pinned()`, `.frozen()`, `.now()`, `.build()`.
**Tests:** IntervalSet table tests; grid rounding (13:12 → ceil 13:15, floor 13:10); local date across midnight.
**Done when:** 100 % line coverage of `timeutil.py`.

### EN-03 — Frames & office gate
**Depends on:** EN-02 **Size:** S
**Files:** `engine/frames.py`
**Tests:** day override extends `latest_block_end`; Saturday has no office; window has exactly `planning_window_days` days; `task_allowed` for High excludes 10:00–18:30 on Mon, not on Sat.

### EN-04 — Meetings, pinned, frozen
**Depends on:** EN-03 **Size:** S
**Files:** `engine/fixed.py`
**Tests:** unit-level only (call `place_fixed` directly on a State): conflicts are detected
against pre-placed occupancy; `PINNED_LEFT_ALONE` logged once per block. The end-to-end pinned
tests (pinned vs prayer conflict, A9) live in EN-11 / EN-15.

### EN-05 — Prayers & qada
**Depends on:** EN-04 **Size:** M
**Files:** `engine/prayers.py`
**Tests:** every bullet in §6.3 "Acceptance checks" + A1 + A2 (window fully booked → qada after Isha, dashed via block_kind `qada`) + drift flag + Jummah day (no Dhuhr in input).

### EN-06 — Habits
**Depends on:** EN-05 **Size:** M
**Files:** `engine/habits.py`
**Tests:** ideal placement; ideal slot taken by meeting → nearest slot (`HABIT_MOVED`); literal
pressure → `HABIT_FIT_COMPRESSED` with exact length; hard habit can't fit → `HABIT_NO_ROOM`;
skipped occurrence → no block; weekly habit only on its weekday; `active_from` respected;
window passed today → no block today.

### EN-07 — Chunking
**Depends on:** EN-02 **Size:** S
**Files:** `engine/chunking.py`
**Tests:** the table in §6.7 + `merge_units` cases ([15,15,15] m=30 → [30,15]→[45]; [45] → [45]; [10] → [10]).

### EN-08 — Ordering & dependencies
**Depends on:** EN-01 **Size:** S
**Files:** `engine/ordering.py`
**Tests:** gate table §6.6; previously_flagged first; null deadline last; topo order with a chain
A→B→C where C has the earliest deadline (C still after B after A); cycle → blocked.

### EN-09 — Task slot search (no shrink)
**Depends on:** EN-06, EN-07, EN-08 **Size:** L
**Files:** `engine/tasks.py`
**Tests:**
- High task on a weekday never lands in 10:00–18:30.
- Buffer: High chunk 18:30–20:00 then next chunk not before 20:15.
- Deadline respected; deadline_first places the latest possible slot.
- Hint kept when still valid (`TASK_KEPT_SLOT`), dropped when a meeting now covers it.
- Dependency: B after A's last chunk end + A's buffer; A flagged → B blocked with chain.
- Deferred until Thu → nothing before Thu.
- 20m task placed whole (D-25); 3h 30m task with only 3h free → 3h placed + `TASK_PARTIAL_FLAGGED` short 30 (first half of TSK-5 acceptance).
- Atomic 105m with only 90m gaps → `TASK_ATOMIC_NO_FIT`.
- Overflow: deadline Thu, only Fri free → chunk on Fri with `meta.overflow`, flag stays (D-24).
- `deadline_first` with a block right after the interval leaves room for the buffer.
- est 50 with grid 15 → treated as 60 (D-26).
- Frozen running chunk reduces need.

### EN-10 — Minimal shrink
**Depends on:** EN-09 **Size:** M
**Files:** `engine/shrink.py`
**Tests:** A3, A4, hard habit, head-vs-tail choice (free time before the habit → head shrink
chosen when it needs less), never below min (property), shrink only when deadline exists.

### EN-11 — Planner orchestration & precedence
**Depends on:** EN-10 **Size:** M
**Files:** `engine/planner.py`, `engine/flags.py`, `engine/why.py`
**Tests:** pinned overlapping a prayer → `PINNED_CONFLICT` and both present; A9 (pinned Tue
21:00 never appears in output blocks, its minutes reduce the task's need — no duplicate chunk);
default order end-to-end day; **reordered** precedence (habits above prayers) → a
habit keeps its slot and Dhuhr shifts around it; office_hours moved below tasks → High task
may enter office hours; settings with non-default buffers/min chunk are honoured (proves SET-0).

### EN-12 — Invariant checker
**Depends on:** EN-11 **Size:** S
**Files:** `engine/invariants.py`
**Tests:** hand-craft a broken output for each invariant → raises with the right code.

### EN-13 — Diff, classification, requires
**Depends on:** EN-11 **Size:** M
**Files:** `engine/diff.py`, `engine/classify.py`
**Tests:** exact match → no change; same-day move safe; cross-day move ask; habit resize safe;
create inside a released interval for a flagged task (A5 after a skip) → safe; create into free time ≥ 60 min ahead → safe; create starting in 30 min → ask; create that needs a
habit shrink → ask; create for a flagged task → ask; `auto_apply_creates="never"` → ask; delete after task done → safe
`PRECLEAN_SOURCE_CLOSED`; requires closure; deterministic change ids; idempotence §8.6.

### EN-14 — What-if
**Depends on:** EN-13 **Size:** S
**Files:** `engine/whatif.py`
**Tests:** A5 — from A4's state, skipping the habit occurrence makes the 30m remainder
placeable and the flag disappear; result reports the new chunk start.

### EN-15 — Acceptance & property suite
**Depends on:** EN-14 **Size:** M
**Files:** `tests/engine/test_acceptance.py`, `tests/engine/test_properties.py`, `tests/engine/test_perf.py`
**Steps:** one test per scenario A1–A5, A9 (A6–A8, A10 are service-level, see 11-testing.md).
Hypothesis strategies generate random days (0–6 meetings, 0–5 habits, 0–12 tasks with random
estimates/deadlines/efforts). Properties: invariants never raise; `plan` is deterministic (two
calls equal); idempotence; habit lengths within bounds; total placed + short == need for each
placed/partial task.
**Done when:** coverage of `engine/` ≥ 95 %, perf test < 500 ms.
