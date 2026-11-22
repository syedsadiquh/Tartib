# 08 — Web Screens (desktop + mobile)

Each screen package lists: **route**, **data** (API + query key), **layout** (desktop, mobile),
**interactions**, **states** (loading / empty / error / offline), **tests**. Mockup references are
for mood. Where this file and a mockup disagree, follow this file.

Feature code lives in `web/src/features/<name>/` with `index.tsx` (route component),
`components/`, `hooks.ts` (if feature-specific), and `*.test.tsx`.

Shared building blocks used by many screens (build them in WEB-10 and reuse):
- `BlockCard` — renders a `Block` from the API (kind styling from `blockStyles.ts`), title,
  subtitle, time range, markers (AI/AUTO/pin/flag), optional right-side actions.
- `Timeline` — vertical day timeline with hour labels, absolute-positioned blocks (1 px = 1 min ×
  scale), "now" line, prayer pills, dashed qada.
- `BlockDrawer` — opens for any block: title, chips, *Why it landed here* (from `placement.meta.why`),
  history (`/api/activity`), actions per kind (Pin time / Split… / Skip / Done / Unpin).

---

### WEB-10 — Today
**Depends on:** WEB-03, BE-17, BE-15, BE-11 **Size:** L
**Spec:** UX-1, OVL-3 badge, PRY next prayer, mockups web/01 (left), web/03 (middle), mobile/01 (Today)
**Data:** `GET /api/today?proposals=true` (`qk.today()`), refetch every 60 s and on focus; `now` line ticks locally each minute. Proposal ghosts are drawn on the timeline (WEB-20).
**Desktop layout:**
- Header: "Today" · `Sat 23 Nov · 3h 25m left · 1 habit needs you` · view switch `Day | Week | List` · ⇄ Re-plan (n).
- Stat strip (4 tiles): Planned · Done · Left · Slack (mono numbers, Done in `--ok`).
- Main: `Timeline` for the day (05:00 → latest block end, auto-scroll to now − 1h).
- Context panel (right, tabs `Now | Next | Habits`):
  - **In progress** card: current block with progress bar, `+15m` `+30m` `Done…` buttons (one gesture).
  - **Habits today** list: checkbox tick (one tap), `Skip` pill, warning text "one more ends it".
  - **Engine notices**: last 24 h shrink/held/release entries ("Compressed, not displaced…").
  - **Up next**: next 3 blocks.
  - **Flags**: red card if `flags_count > 0` → link to `/decisions`.
**Mobile layout (mobile/01 Today):**
- Title "Today", subtitle, streak pill.
- **Next prayer card** (gold): name, time, countdown, circular % ring.
- **NOW** section: current block card with `+15m · +30m` inline; tap card → `BlockDrawer` bottom sheet.
- Compact agenda list of remaining blocks (time column + card), prayers as gold outline pills, qada dashed.
- FAB `+` → capture.
**Interactions:**
- Tick habit → optimistic, `POST /api/habits/{id}/log {done:true}`, undo toast.
- Skip habit (tap pill) → `POST …/skip {scope:"today"}`; toast shows consequence from response
  ("Skipped Gym today · 18:30 opened for W2D2" + Undo). Long-press → skip-until sheet (WEB-18).
- `+15m` → `POST /api/placements/{id}/progress {minutes:15}`.
- Click any block → `BlockDrawer`. Drag is **not** available on Today (only Week) to avoid accidental pins.
**States:** empty day → EmptyState with "Add a task" and "Import from calendar" (onboarding link);
offline → cached view + banner; flags → red dot on header.
**Tests:** renders fixture; tick habit optimistic + undo; +15m call; mobile snapshot at 390 px.

### WEB-11 — Week (desktop grid)
**Depends on:** WEB-10, BE-15 **Size:** L
**Spec:** ENG-3 pin-on-move, A9, mockup web/05, interaction budget #7 ("dragging pins it — no extra save")
**Data:** `GET /api/week?from=&proposals=true` (`qk.week(from)`); prev/next week arrows; "This week". Proposal ghosts overlay the grid (WEB-20).
**Layout:** 7 columns (Mon→Sun or settings week start), hour gutter, header row per day:
`Sat 22 · 2h 45m done`, deadline count, overload badge "FLAGGED: 1h 30m short". Office hours
shaded band per weekday; day frame outside earliest/latest greyed. Blocks positioned by time.
**Drag & drop (@dnd-kit):**
- Draggable: task chunks and habits (engine or pinned). **Not** draggable: meetings, prayers, qada.
- Snap to slot granularity (from settings). While dragging, show ghost + time label; invalid drop
  zones (over a meeting/prayer/qada) are tinted red and drop is refused.
- On drop → `POST /api/placements/{id}/move {start,end}` → block becomes pinned (pin badge), undo
  toast "Pinned W2D2 to Tue 21:00 · Undo". The engine re-plan that follows appears as the ⇄ badge
  count — the user reviews any knock-on moves in the sheet (nothing else moves silently).
- Resize handle (bottom edge) on task chunks → same endpoint with new end (pins).
- **Over a meeting is allowed** (D-15): dropping onto a meeting shows a hatched "over meeting"
  overlay and succeeds; dropping onto a prayer or qada is refused.
- **Unscheduled tray** (collapsible, left of the grid): inbox/flagged tasks with remaining
  minutes. Dragging one onto the grid → `POST /api/placements {task_id, start, end}` (default
  length = min(remaining, max chunk); resizable after). It is created pinned.
- **Past slots are allowed** (D-15): dropping a task or habit onto a time that has already ended
  means "I worked on this then". The confirmation toast says "Logged 45m on W2D2 (during Standup)"
  with Undo, and the block appears solid with a ✓.
- Right-click block → context menu: Open · Pin here / Unpin · Mark done · Defer to tomorrow (tasks) · Skip (habits).
**Tests:** drag a task chunk 2 h later → API called with snapped times; drop on prayer refused;
pinned badge appears after success.

### WEB-12 — Week (mobile agenda)
**Depends on:** WEB-10 **Size:** M
**Spec:** UX-7 (no 7-column grid < 768 px), mockup mobile/01 Week
Grouped list by day: header `SAT 22 · TODAY · 2h 45m done` (accent), rows `time · coloured bar ·
title · duration/state`. Day with overload: red header "THU 27 · FLAGGED: 1H 30M SHORT" and a
"would shrink" note on affected habits. Tap row → BlockDrawer. Swipe row left → "Tomorrow" (tasks: defer; habits: skip) with undo.
Sticky "OVERLOAD" footer card when any day is flagged → `/decisions`.

### WEB-13 — Tasks list
**Depends on:** WEB-03, BE-07, BE-09 **Size:** L
**Spec:** TSK-*, AGT-7, AGT-8, mockups web/01 (middle), web/09 (right), mobile/01 Tasks
**Data:** `GET /api/tasks?…` (`qk.tasks(filters)`); counts from response.
**Desktop:** header "Tasks · 6 in inbox · 4 scheduled · 2 overdue · 14 in backlog", buttons
`+ New task` and `⇪ Bulk import`. Tabs: `All · Inbox · Scheduled · Overdue · Flagged · Backlog ·
Done · By agent · Auto-approved · Created by me` (AGT-8). Search box (`/` focuses).
Table columns: checkbox · Task (title + second line: dependency / gate reason / "AI" marker) ·
Subject · Est · Priority badge · Calendar chip (colour dot) · Deadline (red if overdue, amber if
< 24 h) · Split · Last change ("created 10:41" with AI/AUTO markers). Group sections: OVERDUE,
INBOX — NEEDS EST/PRIORITY/CALENDAR, SCHEDULED, BACKLOG.
Row actions on hover: Done ✓ · Defer ⏭ · ⋯ (Open, Move to backlog, Delete (undo)).
Multi-select → bulk: Set calendar, Set priority, Move to backlog, Defer.
**Mobile:** cards (title, est · state · deadline, priority badge, red gate text), sections OVERDUE /
INBOX. **Swipe** right → Schedule (runs plan for it) / left → Backlog; long-press → Pin / Defer
sheet. Bottom capture bar `+ 2h DBMS revision before friday, high` (NL capture).
**Tests:** tab filters map to query params; overdue styling; AI marker visible for agent tasks;
swipe left calls state backlog with undo.

### WEB-14 — Capture (manual form + NL)
**Depends on:** WEB-13, BE-07, BE-22 **Size:** L
**Spec:** CAP-1, CAP-2, CAP-5, CAP-6, CAP-7, CAP-8, UX-5
Opened by FAB / ⌘N / `c` / palette. Desktop: centered sheet 560 px; mobile: bottom sheet.
**Single input line on top** (placeholder "2h DBMS revision before friday, high"). As the user
types, the **local** parser (a TS port of the deterministic rules, `features/capture/parse.ts`,
reading vocab + inference settings from `/api/settings`) fills **chips** live: Est · Priority ·
Deadline · Subject · Calendar · Effort. **No network call while typing** (CAP-5, CAP-7).
An explicit "✦ Parse with AI" button (only shown when `llm.enabled`) calls
`POST /api/capture/parse {use_llm:true}`; its result fills the **same chips/fields** (CAP-8),
fields it changed get a subtle "AI" underline.
**Manual form parsing, no AI (D-19):** the Estimate field accepts `1h30`, `1h 30m`, `90m`,
`1.5h`; the Deadline field accepts `fri`, `tomorrow`, `tomorrow 5pm`, `next week`, `25 nov`
(normalised on blur, shown as "Fri 28 Nov 23:59"); the Title field runs the same local parser and
fills **only empty** fields, marked *inferred* with × to clear. The same `parse.ts` module is used.
Below: the **form** — three visible fields (Title, Estimate, Priority), disclosure "More" →
Deadline, Effort, Split, Subject, Calendar, Depends on (task combobox), Min chunk, Subtasks
(add rows with weights; footer shows "weights 40 + 30 + 35 = 105 of 105"), Notes, Defer until.
Defaults: last-used subject & calendar remembered in localStorage (CAP-6); calendar auto-set from
subject (shows "auto" tag, still editable).
Keyboard: Tab order = reading order; `Enter` saves; `⌘/Ctrl+Enter` saves **and** runs the plan
(opens review sheet). Inline validation (red text under field), never a modal.
If Est/Priority/Calendar missing → save still allowed; toast "Saved to inbox — needs a calendar"
(CAP-2, SET-3).
**Tests:** parser parity — run the backend parser test table through the TS parser (export the
cases as JSON fixtures shared by both suites: `backend/tests/fixtures/parser_cases.json`, copied
to `web/src/features/capture/__fixtures__` by `make gen-api`); Enter saves; ⌘Enter opens review;
no fetch while typing (assert MSW saw zero calls).

### WEB-15 — Task detail drawer
**Depends on:** WEB-13, BE-18 **Size:** M
**Spec:** TSK-8, G4, AGT-7, mockups web/02 (left) & web/06 (right)
Header: breadcrumb (`cybersec · Week 3 · Day 3`), title (inline editable), chips: priority, est,
due, units, depends-on, state, AI/AUTO markers.
Sections:
1. **Subtasks** — checklist with weights; `SegmentedProgress`; "weights 40 + 30 + 35 = 105".
2. **Placement** — mini week strip showing this task's blocks (filled = done, hatched = pending, red = flagged).
3. **Properties** (editable, save on change): Effort, Estimate, Logged, Deadline, Split, Min chunk, Depends on (✓ when done), Buffer after (read-only, from effort), Calendar, Subject.
4. **Why it landed here** — bullets from the next block's `meta.why`.
5. **What blocked here** — when flagged: the flag detail ("Thu 18:30 held by Gym. Gym would compress to its 60m minimum and still not free enough…").
6. **History** — `/api/activity` list ("Today 09:41 — engine → Sat 18:00", "Yesterday — you moved it to Sat 20:00 (pinned)").
Footer actions: **Pin time** (opens time picker → move endpoint) · **Split…** (edit subtasks) · **Skip** (state skipped, undo) · Done.

### WEB-16 — Bulk import & review table
**Depends on:** WEB-13, BE-22 **Size:** L
**Spec:** CAP-3, UX-10, AGT-11, mockup web/08, wireframe 06
Step 1 (sheet): textarea "Paste a syllabus, list or chat dump" + live preview of the first lines;
"Parse" → `POST /api/tasks/bulk {mode:"parse"}` → navigate `/tasks/import/:batchId`.
Step 2 (page): header "Review import · 18 tasks parsed · check Est, Priority and Calendar before
committing", source tag (e.g. "from agent: assistant-bot · pasted syllabus"), stat strip `PARSED · COMPLETE ·
MISSING EST · NO CALENDAR · WILL SCHEDULE · WILL FLAG`.
Table grouped **NEEDS A DECISION — n** (rows missing any of Est/Priority/Calendar) then **READY — n**.
Columns: include checkbox · Task (title + note like `parsed "1h 45" as unknown unit`, `after W2D5`) ·
Subject · **Est** · **Priority** · **Calendar** (chip with "auto" tag when inferred) · Deadline · edit ✎.
Every cell is inline-editable (click → input/select; Enter saves via PATCH row). Moving a row
from NEEDS to READY happens live when fixed.
Footer: "14 will be scheduled · 4 stay in inbox until Est or Calendar is set · nothing is
written to Google Calendar yet" + buttons `Edit as text` (back to textarea with current rows
serialised) · `Save 14 to inbox` · **`Commit & preview plan →`** (gold) → commit with
`then_plan:true` → opens review sheet.

### WEB-17 — Habits screen & editor
**Depends on:** WEB-03, BE-10, BE-11 **Size:** L
**Spec:** HAB-*, mockups web/01 (right), mobile/01 Habits, mobile/04
**Desktop:** header "Habits · 5 active · 87% this week · compress under pressure, never displaced"
+ `+ New habit`. Grid of habit cards (2 columns): name, weekday letters (active ones bold), chips
`3h → min 60m`, window `06:00–09:00 · not before 06:00`, StreakDots (last 7 occurrences), status
line (green "no compression this week" / amber "compressed 3× this week" / red "one more ends
it"), today's action row (Tick · Skip). Hard habits show "never compressible". Ended habits show
in an "Ended" section with **Reactivate**. Archived (deleted) habits under "Ended <date>" collapsed.
Right panel: **"Under pressure — what happens"** explainer (4 numbered rules from mockup, text
generated from settings: shrink to minimum, notify, skip frees time, otherwise flag) and the
selected habit's **Edit** form.
**Habit editor** (sheet on mobile, right panel on desktop; user-only — hide for agents):
Name · Days (7 toggle chips) · Ideal duration · Minimum (with "hard habit" hint when equal) ·
Window not before / not after · Ideal time · Priority · Compressible switch (disabled & off when
hard) · Calendar. Live preview text: "Under pressure compresses to 60m".
Create uses POST; edit saves on change (PATCH). **Delete** (only via ⋯ menu / long-press menu)
→ ConfirmDialog with consequence "Gym ends today. Future blocks are removed. Past 46 occurrences
stay in Insights. Nothing is marked missed." (UX-3, HAB-11).
**Mobile:** list of habit rows (checkbox circle, name, sub-line "3h logged · min 60m", dots,
`Skip` pill or `+15m` for duration habits). Rule card on top. "If a high task needs this slot"
3-step chip row (1·Shrink to min · 2·Notify · 3·Skip = free).

### WEB-18 — Skip, skip-until, delete, reactivate flows
**Depends on:** WEB-17 **Size:** M
**Spec:** HAB-6, HAB-8, HAB-8a, HAB-10, HAB-12, A6, A7, mockups mobile/02–04
- **Skip (tap):** immediate; toast with consequence + Undo.
- **Skip until… (long-press / ⌥ in palette):** sheet with quick picks (Tomorrow · End of week ·
  Next week · Pick date) → on pick, call `GET /api/habits/{id}/skip-preview?until=` and show the
  **consequence block before confirming**: "3 occurrences fall in this span — this will end your
  14-day streak on Thu 26." (red when `will_end_streak`). Button label changes to "Skip and end
  streak" in that case. Plus freed-time line from what-if.
- **Streak states** on cards: held (1 skip, grey note "skipped yesterday · streak held at 14"),
  warning (2 skips, amber "one more ends the streak", `1 left` pill), ended (red ✕, "3rd skip
  today · streak 9 → 0", **Reactivate** button).
- **Reactivate sheet:** stats (46 occurrences · 9 best streak · 12 compressed), two options:
  "Reactivate from today — schedules tonight 19:00 if a slot exists" / "Reactivate from tomorrow — starts fresh Mon 24".
  Footer text: "Past data is never deleted…".
- **Delete:** see WEB-17.
**Tests:** preview text shown before confirm; ended card shows Reactivate; reactivate calls API with `from`.

### WEB-19 — Prayers
**Depends on:** WEB-03, BE-12 **Size:** M
**Spec:** PRY-*, mockups web/02 (middle), mobile/01 Prayer, mobile/02
**Desktop:** header "Prayers · {location} · {method} method · {timezone} · 0 tasks can overlap",
`Edit times` → `/settings/prayers`. Today list rows: name · time (mono) · duration · status text
("next · in 1h 42m", "done", "after sunset · 17:02 computed", "last block of the day") · tag
(`fixed` / `computed ±10` / `shifted` / `qada #1` dashed). Next prayer row highlighted gold.
**Next 7 days** compact grid (7 columns × prayers, Friday shows Jummah). Right panel: rule card
("Prayers outrank everything except meetings…"), "What each prayer is" (fixed/computed times),
notifications (adhan push), **drift guard** card (amber when drift flag), location & method.
**Mobile:** big countdown ring (next prayer, time, "in 1h 42m"), list for today, "TOMORROW" list, rule card.
**Interactions:** tap a prayer/qada row → sheet with `Mark prayed` (one tap, PRY-5/6, undo) and
for qada: `Move earlier & mark prayed` (time picker). Shifted prayers show "moved 13:00 → 13:20 ·
meeting until 13:15" (A1 copy) — mobile/02.

### WEB-20 — Plan review on the calendar (the trust loop)
**Depends on:** WEB-10, WEB-11, WEB-12, BE-13, BE-14 **Size:** L
**Spec:** ENG-2, RPL-2..5, UX-3, G4, **D-14, D-28**, mockup web/06 (left, now a side panel)

**Idea:** the user sees the proposal *in place*. Today and Week always draw the current proposal
as hollow dashed **ghost blocks** (style in 07-web-foundation §1). Nothing is a separate page; the
⇄ badge, `?review=1`, ⌘R and the notification click all open **review mode** on the Week view
(desktop) or Today/Week agenda (mobile), scrolled to the first change.

**Always-on overlay (WEB-10/11/12 render it):**
- Data: `proposals` from `GET /api/today?proposals=true` / `GET /api/week?…&proposals=true`.
- Ghost at `to`; faded original at `from` + connector for moves/resizes; struck-through original for deletes.
- Header chip `Proposals ●` toggles the overlay (default on, remembered in localStorage).
- Auto-applied blocks (D-14) are normal blocks with the **AUTO** marker; Today's notices show
  "Added 3 blocks automatically · Review" which opens review mode filtered to those blocks.

**Review mode (desktop):** Week grid + right **review panel** (320 px):
- Header: "Re-plan · Sat 22 Nov, 09:41 · 3 changes · **nothing is written until you accept**",
  toggle **auto-apply safe changes** (writes `block_rules.auto_apply_safe`).
- Compact list, one row per change (`[✓] NEW W1D5: Scanning · Sat 18:00–20:00`, second line
  `Why: …`); hovering a row highlights its ghost and vice versa; clicking scrolls the grid to it.
- Flags after changes (non-checkable FLAG rows, "I won't choose for you", "Resolve →" `/decisions`).
- Footer: `2 to apply · 1 not now · 1 flag` · `Reject all` · **`Apply 2 changes`**.

**Actions on a ghost** (popover on click; also in the panel row's ⋯ menu; keyboard: `a` accept
toggle, `n` not now, `l` later date, arrow keys move between ghosts):
- **Accept** (checkbox state; default checked — accept-all stays the default, interaction budget #5).
  Unchecking a change that others `require` unchecks them too ("also unchecks 1 dependent change").
- **Not now** → `POST /api/plan/reject {plan_run_id, change_ids:[id]}` (suppressed 24 h); ghost fades out with undo toast.
- **Later date** (task changes only) → picker *Tomorrow · Next week · Pick date* →
  `POST /api/tasks/{id}/defer {until, replan_now:true}` → overlay refreshes from the returned run;
  toast "W1D5 moved to Mon — new slot proposed" + Undo.
- **Drag the ghost** to another slot (snaps to grid; refused over meetings/prayers/qada) → stored as
  an override for that change and auto-accepted; ghost shows a pin badge ("will be pinned").
- **Open** → BlockDrawer with full *why* bullets.

**Apply:** `Apply n changes` → **ConfirmDialog** (hard confirm #1, UX-3) with a one-line summary
per calendar ("Tasks & Todos: 1 new, 1 moved · Prayers: 1 shifted") → `POST /api/plan/apply
{accept, overrides, confirm:true}`; ghosts turn solid in place (optimistic, reverted on error);
success toast "Applied · Google Calendar updated"; failure panel "Google write failed — nothing
was changed (rolled back). Retry" (RPL-5); 409 `PLAN_STALE` → refetch, "The plan changed while you
were reviewing — updated". Leftover unticked changes stay as ghosts (partial apply keeps the run proposed).

**Mobile:** review mode = Today/Week agenda with ghost rows inline (dashed hollow card, NEW/MOVED
tag, "from 13:15" caption) and a sticky bottom bar `3 changes · Apply`. Tap a ghost row → bottom
sheet with Accept / Not now / Later date / Open. Swipe ghost right = accept toggle, left = Later
date (tomorrow). No dragging of ghosts on mobile (use Later date or Open → Pin time).

**Tests:** ghosts render at `to` with faded `from`; accept-all default; requires-closure
unchecking; Not now calls reject with one id; Later date calls defer with `replan_now` and swaps
the overlay; dragging a ghost sends `overrides`; confirm dialog required; stale → refetch; overlay
toggle persists; qada and ghost are visually distinct (snapshot).

### WEB-21 — Decisions (needs a decision / overload)
**Depends on:** WEB-20, BE-16 **Size:** L
**Spec:** OVL-1..3, D-21, mockup web/03 (right), wireframe 08
Route `/decisions`; badge count in rail and Today header.
Sections (from `GET /api/decisions`):
1. **Overload** cards: title (`cybersec — W2D4: IDOR practice` + FLAGGED), numbers line
   ("needs 3h 30m · 1h 00m available · shrink gave 2h · **30m short**"), chips (High · due Thu ·
   Gym Thu → min 60m · short 30m). **Levers** (loaded lazily from `/levers`): each lever row shows
   label, effect text, cost text, and a ✓ "clears the flag" mark: Push the deadline · Skip a
   habit occurrence · Extend Thu by 30m · Lower W2D4 to 2h 00m (drop a unit). One tap applies
   (undo toast) → re-plan → review badge. Footer note: "If you do nothing: W2D4 keeps its flag…
   exactly one reminder tomorrow morning — not hourly." (OVL-3).
   Right panel: **"The shrink rule, stated once"** + **"Shrink math — this task"** (Gym Thu 3h →
   min 60m · flex 2h · shrink applied 2h · task still short 30m) from the flag numbers.
2. **Needs fields**: tasks missing Est / Priority / Calendar — inline editors right in the row.
3. **Blocked**: dependency chains ("W2D6 blocked by dependency — starts only after W2D4 lands"), pinned conflicts with "Unpin" action.
4. **Agent proposals**: held agent actions with summary + Approve / Reject.
5. **Prayer drift**: drift card with "Open prayer settings".
Empty state: "Nothing needs you. The plan is honest."

### WEB-22 — Engine log
**Depends on:** WEB-03, BE-18 **Size:** M
**Spec:** G4, RPL-6, AGT-8, mockup web/03 (left)
Header "Engine log · Every automatic decision, the rule it used, and what it cost" + range `Today | Week`.
Filter chips with counts: `All · Shrinks · Held · Prayers · Released · Flags · Pins · Apply` +
actor filter `Anyone · Me · Agents · Engine`.
Rows: time (mono) · category badge (MIN SHRINK purple / HELD AT FLOOR amber / RELEASED green /
STACKED gold / SHIFTED gold) · title (bold) + detail (muted) · right side effect summary
("2h → 2h 30m / min 60m intact", "+55m capacity · 1 task scheduled") · AI/AUTO markers · undo
button when `undo_token` still valid. Infinite scroll by cursor. Click row → subject drawer.

### WEB-23 — Insights
**Depends on:** WEB-03, BE-23 **Size:** M
**Spec:** INS-1..5, mockup web/02 (right)
Header + range select (Week ▾ / Month). Tiles: **Adherence 78%** (12h 40m of 16h 10m planned) ·
**Habits kept 87%** (20 of 23 occurrences) · **Compressions 9** (habits shrunk, none skipped).
Charts (Recharts, colours from tokens, both themes): Planned vs Done by day (paired bars),
Where the week went (donut by subject, legend with %), Backlog debt (number + overdue trend
bars), **Habit consistency — last 4 weeks** heatmap row per habit (full = solid teal, compressed
= half, skipped = outline, missed = red, ended = gap — never a blank line, HAB-10).
Accessible: each chart has a visually-hidden table alternative.

### WEB-24 — Settings (all sections)
**Depends on:** WEB-03, BE-19, BE-20, IN-01..03 **Size:** L (split into sub-packages a–h if needed)
**Spec:** SET-0..17, mockup web/07
Layout: left section nav grouped **Connections** (Google account, Precedence) · **Engine**
(Calendars, Working hours, Block rules, Prayers, Habit defaults, Task defaults, Vocabularies) ·
**System** (Notifications, Monitoring, Backup & restore, Agent access, Account & security, Audit log).
Header shows "✓ All changes saved live" / "Saving…" / "Couldn't save — retry".
Every field saves on change via `PATCH /api/settings/{section}` (single field) with version.
Each section has **Reset to defaults** at the bottom (confirm, SET-15).
- **a. Google account** (SET-1): connected card (email, "Calendar read/write · N
  calendars found"), status CONNECTED/EXPIRED, Re-authorize, Disconnect (confirm), granted
  scopes, token health, redirect URI field (self-hosting), client id + secret (secret write-only).
- **b. Precedence** (SET-5): 7 draggable rows with descriptions and tags (`read-only`,
  `protected`, `never`); dragging shows the warning banner when a prayer would yield ("Moving
  Prayers below Habits would let a habit hold a prayer's slot and force a Qada. The engine allows
  it — this warning appears whenever your order causes a prayer to yield."); **Preview effect on
  this week** → calls preview endpoint, shows summary list; **Save order** only after preview
  (the one settings change that needs an explicit commit). Backlog row is fixed last.
- **c. Calendars** (SET-2..4): discovered calendars table (colour, name, role, Read meetings ✓,
  Writable ✓, Busy ✓, Enabled ✓) + **routing table** "Default calendar per subject" (Subject/block
  type → calendar chip select → colour) with "+ Add a subject default"; explanatory note "These
  are defaults, not gates…".
- **d. Working hours** (SET-7): 7 rows: office start–end (or "No office"), earliest block,
  latest block end; plus upcoming **day overrides** list.
- **e. Block rules** (SET-8): Placement (min chunk, max chunk, planning window, buffer per
  effort level, slot granularity, earliest/latest defaults), Behaviour (auto-apply safe moves,
  auto-apply creates, ask before cross-day moves, prayer edge guard, max qada per day, streak
  break after, shrink = minimal (read-only), placement order). Info banner "These are the only
  numbers the engine has…". **Danger zone:** "Recompute the whole calendar" (confirm; `POST /api/plan/run {drop_hints:true}`,
  then opens the review sheet — still nothing is written until Apply).
- **f. Prayers** (SET-6): per-prayer rows (enabled, fixed/computed, time, duration, window
  offsets shown as absolute times, edge, notify lead) + Jummah overrides Friday, method, madhab,
  location (name, lat, lon), meeting gap, qada cap, drift threshold, "Show computed vs fixed for
  today" table.
- **g. Habit & task defaults** (SET-9, SET-10) incl. inference rules editor (priority words,
  deadline phrases) with a "Try it" input running the local parser.
- **h. Vocabularies** (SET-17): tabs Subjects · Priorities · Effort · Split modes; sortable list
  (drag), label rename inline, enable toggle, delete (409 → offer disable), subject meta
  (default calendar, priority, effort, keywords).
- **Notifications** (SET-11): 4 types × enable + lead time; quiet hours; channels; "Send test
  push"; device subscription status (WEB-26).
- **Backup & restore** (SET-12): Notion token (write-only), parent page id, frequency,
  retention, last mirror status, **Mirror now**; Restore: **Dry run** → diff viewer (creates /
  updates / unchanged / only in DB) → **Apply restore** (confirm). Settings export/import JSON
  (SET-16) with dry-run diff.
- **Monitoring** (NFR-3/4): Healthchecks ping URL and Discord alert webhook (secrets, write-only,
  via `PUT /api/settings/secrets/{name}`), grace minutes, loud-after-N-misses, last heartbeat and
  last hourly run status, "Send test alert".
- **Account & security** (SET-13): passkeys list (add/remove), sessions list (revoke), theme,
  display name.
- **Audit log** (SET-14): table of `audit_entry` with before/after diff popover.

### WEB-25 — Agent access
**Depends on:** WEB-24, BE-21 **Size:** M
**Spec:** AGT-2..10, mockup web/09 (left)
Token cards: name, `Token sch_ab12…` prefix, created/last used, status ACTIVE/REVOKED, **Revoke**
(available always, AGT-9). Create token sheet → shows the token **once** with copy button.
**Permissions** list (one row each): Read schedule & tasks · Create tasks · Edit task fields ·
Move/reschedule blocks · Apply the plan to Google Calendar — each with a scope switch and an
"auto-approve" switch (disabled unless scope on; caption "auto-approve is per-permission, not
global"). A greyed, permanently-off row: "Delete tasks · edit habits · change settings — never
available to any token" (AGT-3).
Limits: rate limit /hr, daily cap, bulk batch max (AGT-10).
Info banner: "Every agent action is attributed. Anything a token changes carries an AI marker…
AUTO when applied without asking."
**Recent agent activity** list with AUTO / HELD badges.

### WEB-26 — Push subscription & notification actions
**Depends on:** WEB-08, IN-10, WK-04 **Size:** M
Settings → Notifications "Enable on this device" → `Notification.requestPermission()` →
`registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey})` →
`POST /api/push/subscribe`. iOS: show "Add to Home Screen first" hint when not standalone.
SW `push` handler shows notification with tag/actions; `notificationclick`: `done` / `skip`
actions call the API directly (`fetch` with `credentials: "include"` **and header
`X-Requested-With: tartib`**, or the CSRF check returns 403) then focus/open the app; default click opens payload
`url` (e.g. `/today?review=1`).

### WEB-27 — First-run onboarding
**Depends on:** WEB-24 **Size:** M
**Spec:** wireframe 05 ("4 steps, skippable", "first run is read-only")
Stepper: **1 Connect Google** → **2 Location & method** (location empty and **required** for computed prayers;
"Use my location" button or city name + lat/lon fields; method defaults to Karachi) → **3 Office hours** (per-weekday quick editor) →
**4 Calendars & seed habits**: tick meeting calendars and writable calendars; routing table;
detected recurring GCal blocks (server returns recurring events in writable calendars, e.g. Gym,
Freshup) proposed as habits with editable windows and minimums. Finish → first `plan/run` →
review sheet opens. Guard text: "First run is read-only: import + propose. No writes until you
see the first plan." Each step skippable; progress stored server-side (`settings.general.onboarded_steps`).
