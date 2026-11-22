# Tartib — Engine & Interaction Spec

Status: rules agreed through 22 Nov. This is the build contract: if code and this
document disagree, the document is wrong and must be changed first.

---

## 1. Precedence (highest → lowest)

1. **Office meetings** (Google Calendar, read-only)
2. **Prayers**
3. **Office hours** (High effort cannot enter)
4. **Pinned blocks** (anything the user moved)
5. **Habits**
6. **Tasks** (by deadline pressure)
7. **Backlog** (never scheduled)

Everything below the line yields to everything above it. A lower rank never displaces a
higher one; where it can't fit, it is flagged (see §8).

---

## 2. Time model

- Timezone: Asia/Kolkata (IST) for all writes.
- Planning window: 14 days rolling.
- Minimum chunk: 30m. No block shorter than 30m is ever created.
- Buffers: 15m after High, 10m after Medium, 0m after Low.

---

## 3. Prayers

Fixed preferred times (canonical) with a computed library cross-check:

| Prayer | Time | Duration |
|---|---|---|
| Fajr | 05:15 | 30m |
| Dhuhr | 13:00 | 30m |
| Jummah (Fri) | 12:45 | 60m |
| Asr | 15:35 | 25m |
| Maghrib | computed (≈17:05) | 20m |
| Isha | 19:45 | 45m |

### Collision with a meeting
Each prayer has a **window**. The first and last **10 minutes of the window are
protected** and never used. A prayer must fit entirely inside the core
`[window_start + 10m, window_end − 10m]`.

1. If the meeting overlaps, **shift the prayer inside the core**.
2. If it cannot fit in the core at all, **move it to Qada**, placed **after Isha only —
   never before Isha**.
3. Multiple qadas **stack** after Isha in any order. Order does not matter.

### Qada is a placeholder, not a grave
- While pending, **no task may ever take a qada block**. Only the user clears it.
- The moment the user marks it prayed — or moves it earlier and prays it — the remaining
  time **returns to normal capacity**.
- Freed capacity is refilled **flagged tasks first**, then by deadline pressure.
- A freed slot **never** displaces a pinned block.

### Invariants
- A prayer never moves for a habit, a pinned block, or a deadline.
- Tasks never land on a prayer or a qada block.
- Drift guard: if the computed time and the library differ by >10m, flag it — never
  silently move the evening.

---

## 4. Habits

Fields: name, weekday set, **ideal** duration, **minimum** duration, window (not before /
not after), ideal time, priority, compressible flag.

### Shrink rule (the core mechanic)

```
shortfall = task_need − free_capacity_before_deadline
flex      = habit_ideal − habit_min
shrink    = min(shortfall, flex)
```

- Shrink is **minimal**: exactly what the task needs. If 30m is enough, shrink 30m — not
  a percentage, not a ladder.
- If the shortfall exceeds the flex, **take the whole flex** (down to the minimum),
  schedule what fits, and **flag the rest**.
- The minimum is **absolute**. Never cross it.
- `min == ideal` means a **hard habit** — never compressible (e.g. Qur'an 15m).

### Reset
Compression **resets daily**. Each day starts at the ideal duration unless something
shrinks it again that day. Compression count per week is recorded for display only
("compressed 3× this week") and never degrades the base.

### Resolving a blocked habit's slot
Preference order before touching a habit:
1. Free slot elsewhere, same day
2. Free slot on a later day before the deadline
3. **Shrink the habit** (last resort, minimal)
4. Flag and stop

### Skip / pause / delete

| Action | Reach | Effect on streak | Blocks |
|---|---|---|---|
| **Skip** (1 tap) | This occurrence | Counts as a skipped occurrence | Released immediately |
| **Skip until…** (long-press) | User-picked span | Every occurrence in the span counts as skipped | Released for the span |
| **Delete** | Permanent | Ends the habit; **nothing is marked missed** | All future blocks removed |

- A deleted habit has no occurrences, therefore **nothing can be missed**. History is
  archived under "Ended <date>".

### Streak break rule — three consecutive skipped occurrences
Counting is **per habit occurrence, never per calendar day**. A weekly habit breaks after
three skipped weeks, not three days.

- **1 skipped occurrence** → streak holds.
- **2 consecutive** → streak holds, and the card warns: *"one more ends it"*.
- **3 consecutive** → **streak resets to 0** and the habit is marked **ended**.
- Logging the habit at any point **resets the counter to zero**.

### Skipping is not free
There is **no exemption for "Skip until…"** — every occurrence inside the span counts.
The cost of pausing is the loss of the streak, deliberately. Rationale: it discourages
reflexive skipping and makes consistency visible as the thing that is being spent.

A genuine miss (day passes unlogged and unskipped) breaks the streak immediately;
skipping is the only way to pause at all, and it is still counted.

### Reactivate
An ended habit is reactivated from the card:
- The streak **restarts at 0**.
- **All past data is kept** — occurrences, best streak, compression count remain in the
  record and in Insights. The streak chart shows the gap, never a blank line.
- Reactivate from today or from tomorrow; today only schedules if a slot exists.

### Skip is a gain, not a loss
Every skip surfaces the consequence inline: *"frees 18:30 → W2D2 can start today."*

---

## 5. Tasks

Fields: title, estimate, priority, deadline, effort (High/Med/Low), split
(Atomic/Subtasks/Auto), subtasks with weighted minutes summing to the estimate,
depends-on, min chunk.

### Scheduling gates — why a task can't be placed
- no estimate **or** no priority → blocked
- dependency not complete → blocked
- no slot after Isha before the deadline → flagged
- habit minimum in the way → waits, then flags
- a pinned conflict → blocked on the pinned block

### Partial progress
"45m of 90m logged" returns the remainder to the pool, re-chunked to ≥30m.

### Partial scheduling (when it can't fully fit)
1. **Schedule the amount that fits**, do not hold the task back.
2. **Flag the remainder** — it is crossing the deadline.
3. When the user frees time (skip a habit, extend a day), **the remainder is
   rescheduled** to bring the task to full.
4. If time never opens, the remainder **splits to later free time** and keeps its flag.

A task is never silently dropped and never silently overbooked.

### Defer (task-level "skip until")
A task may be deferred to a date. Deferring moves no deadline unless stated, is written to
history, and carries **no penalty** — streaks are a habit concept only. Unlike a habit
skip, deferral is free.

---

## 6. Re-plan loop

```
trigger (hourly / change / manual)
  → engine dry run
  → diff
  → classify each change → notify
  → user accepts
  → write to Google Calendar
  → log history
```

**Safe to auto-apply:** move within the same day; shrink a habit to fit.
**Must ask:** move across days; drop or skip anything; push a deadline.
**Never:** touch a pinned block.

Failure path: GCal write fails → retry once → roll back the diff → alert. Never leave a
half-applied plan.

---

## 7. Precedence of resolution (task placement)

For each unscheduled task, in deadline order:
1. Best free slot satisfying effort gates, dependencies, buffers, min chunk
2. If none on the deadline day, try earlier days within the plan window
3. Only then shrink a habit (§4) — minimal, and only the habit blocking the
   deadline-critical slot
4. If still impossible, **flag and stop** (§8)

Shrink is always the last resort, never the first move.

---

## 8. Overload — flag and stop

When required capacity exceeds available capacity, the engine **stops and reports**:

- Names the exact shortfall (`3h 30m needed · 1h 00m available · 30m short after max shrink`).
- Offers, never chooses:
  - **Push to next week** (deadline moves with it)
  - **Skip a habit occurrence** (frees a block)
  - **Make time** (extend the day / use the office→evening gap)
  - **Reduce the task** (drop a subtask)
- If the user chooses nothing: the task keeps its flag, the flag badge stays on Today,
  and there is **exactly one reminder the next morning** — never hourly.

---

## 9. Notion — bookkeeper only

- Source of truth is **Postgres**. Notion is **never read during normal scheduling**.
- A **write-only mirror** runs after every plan application.
- Restore path: pick snapshot → diff vs Notion → rehydrate tasks & habits → re-plan once
  → review the delta.
- Mirrored fields: title, estimate, priority, deadline, effort, split, subtasks,
  depends-on, placement history (append-only log).

---

## 10. Interaction budget

Top actions must cost **one gesture**: tick habit · skip habit · log +15m on the current
block · capture a task · accept the plan.

Rules:
- **Undo beats confirm** — 10-second toast on everything reversible.
- **Tap = the obvious action; long-press = the alternative.**
- **Never ask what can be inferred** — estimate from the last similar task, priority from
  subject, deadline from "before Fri".
- **Only two hard confirms:** applying the plan to Google Calendar, and deleting a habit.
- Minimum chunk and buffers are silent; never ask the user to set them per task.

---

## 11. Resolved & closed

- **Hard habit last resort** — a hard habit (`min == ideal`) is simply never compressed.
  If it is the only blocker, the task flags; the engine never asks to override.
- **"Make time" may not touch office hours.** Office hours are a fixed constraint; the
  levers are push deadline, skip a habit occurrence, extend the day's edge, or reduce the
  task.
- **Mobile week view is an agenda list**, not a 7-column grid — 390px cannot render 7
  columns legibly.

Nothing is currently open. New rules go here first, then into the code.
