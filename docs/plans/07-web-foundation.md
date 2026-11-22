# 07 — Web Foundation: Design System, Shell, Data Layer, PWA

One codebase (`web/`) serves the desktop web app and the installable mobile PWA. Layout switches
at **768 px** (UX-7). The mockups set the mood (dark, dense, calm); this file is the binding spec.

## 0. UX principles (apply to every screen)

1. **Density over whitespace** (UX-9): 13 px base text on desktop, 15 px on mobile; 28–32 px row
   heights on desktop tables; 44 px minimum touch targets on mobile.
2. **One gesture for the top five** (UX-1): tick habit · skip habit · +15m on current block ·
   capture · accept plan. Each must be reachable without opening a modal.
3. **Undo beats confirm** (UX-2): every reversible action shows a 10 s toast with **Undo**. Only two
   hard confirms exist (UX-3): *apply plan to Google Calendar* and *delete a habit*. (Destructive
   settings actions in SET-14 also confirm — they are settings, not daily actions.)
4. **Show consequences inline** (UX-6): skip, shrink and lever buttons show what they free or cost
   *before* the tap ("frees 18:30 → W2D2 can start today").
5. **Every automatic change is explainable** (G4): any block opens a drawer with *why it landed
   here* and its history.
6. **Color is never the only signal**: every block type has an icon + label; flags have text.
7. **Save on change** — no Save buttons in Settings or forms that edit existing items; show an
   inline "Saved" tick. (The manual task *create* form keeps an explicit Enter / Save.)
8. **Keyboard-complete on desktop**: ⌘K palette, shortcuts list (`?`), visible focus rings.

### Improvements over the mockups (approved latitude in the brief)
- **Decisions inbox** — one place (and one badge) for everything waiting on the user: overload
  flags, tasks missing Est/Priority/Calendar, held agent proposals, prayer drift, pinned conflicts.
  The mockups scatter these across Today, Tasks and Prayers.
- **Plan review happens on the calendar** (D-28): proposals are hollow dashed ghost blocks on
  Today and Week, with Accept / Not now / Later date / drag right on the block; a compact side
  panel (desktop) or bottom bar (mobile) holds the list and the Apply button.
- **Persistent "Now" strip** on mobile Today: current block + next prayer in one 72 px card with
  +15 / +30 / Done.
- **Precedence rail doubles as the colour legend** (each rank shows its block colour swatch).
- **Light theme** in addition to dark (system preference by default; toggle in Settings → Account).
- **Empty states** that teach (wireframe 05): "Nothing scheduled yet — add one task or let it import your calendar."
- **Skeleton loaders**, never spinners, for lists and timelines.

---

## 1. Design tokens (`web/src/design/tokens.css`)

CSS variables on `:root` (dark default) and `[data-theme="light"]`. Tailwind v4 `@theme` maps
them to utilities (`bg-surface`, `text-muted`, `border-line`, …).

```css
:root, [data-theme="dark"] {
  --bg:          #0b0d12;  --surface:  #12151c;  --surface-2: #181c25;  --surface-3: #1f2430;
  --line:        #252b38;  --line-strong: #323a4b;
  --text:        #e7e9ef;  --text-muted: #8b92a5;  --text-faint: #5d6478;
  --accent:      #8b5cf6;  /* primary actions, tasks  */  --accent-ink: #ffffff;
  --task:        #8b5cf6;  --task-bg: rgba(139,92,246,.14);
  --habit:       #2dd4bf;  --habit-bg: rgba(45,212,191,.12);
  --prayer:      #e0a84a;  --prayer-bg: rgba(224,168,74,.12);
  --qada:        #e0a84a;  /* drawn dashed */
  --meeting:     #64748b;  --meeting-bg: rgba(100,116,139,.18);
  --pinned:      #f5c451;
  --flag:        #ef6b6b;  --flag-bg: rgba(239,107,107,.12);
  --warn:        #f59e0b;  --ok: #34d399;  --info: #5b8def;
  --ai:          #a78bfa;  /* AI marker */   --auto: #38bdf8; /* AUTO marker */
  --radius-sm: 6px; --radius: 10px; --radius-lg: 14px;
  --shadow-sheet: 0 20px 60px rgba(0,0,0,.45);
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;   /* times, durations, counts */
}
[data-theme="light"] { --bg:#f7f7fa; --surface:#ffffff; --surface-2:#f1f2f6; --surface-3:#e8eaf0;
  --line:#e2e5ec; --line-strong:#cfd4de; --text:#151821; --text-muted:#5b6275; --text-faint:#8a90a2;
  /* keep hues, darken for contrast: */ --task:#6d3fe0; --habit:#0f9f8f; --prayer:#b7791f; --flag:#d64545; }
```
Typography scale: `xs 11/14`, `sm 12/16`, `base 13/18` (desktop) / `15/20` (mobile), `lg 16/22`,
`xl 20/26`, `2xl 28/32` (stat numbers, mono). All times and durations use `font-mono tabular-nums`.
Contrast: text on surfaces ≥ 4.5:1 (check with the design:accessibility-review skill or axe in e2e).

Block colour mapping (single source: `design/blockStyles.ts`):
| kind | left bar | background | icon (lucide) | extra |
|---|---|---|---|---|
| meeting | `--meeting` | `--meeting-bg` | `Briefcase` | read-only |
| prayer | `--prayer` | `--prayer-bg` | `Moon` | pill shape on timeline |
| qada | `--qada` | `--prayer-bg` (filled) | `MoonStar` | dashed gold border + "QADA" label |
| habit | `--habit` | `--habit-bg` | `Repeat` | "min protected" subtitle if at floor |
| task_chunk | calendar colour or `--task` | `--task-bg` | `CheckSquare` | effort chip |
| pinned (any) | `--pinned` | as kind | `Pin` | small pin badge top-right |
| **proposal (ghost, D-28)** | dashed 1.5 px border in the kind's colour | **none (hollow)** | kind icon | top-left tag NEW / MOVED / RESIZED / REMOVED; `safe` changes slightly less prominent; on hover/focus show Accept · Not now · Later date |
| proposal "from" position | — | kind bg at 35 % opacity | — | dotted connector line to the ghost (Week grid) or "from 13:15" caption (agenda) |
| proposal delete | kind colour, struck-through title | kind bg at 35 % | — | red dashed outline |

Ghosts are distinguished from qada by **fill** (ghosts are hollow, qada is filled) and by the
tag, never by dashes alone.

## 2. Core components (`web/src/design/components/`)

Build each with Radix where noted, Tailwind classes, `forwardRef`, full keyboard support, and a
Vitest + Testing Library test for its interactive behaviour.

| Component | Notes |
|---|---|
| `Button` | variants: primary (accent), secondary, ghost, danger, gold (capture/commit, matches mockup CTA); sizes sm/md; `loading` state |
| `IconButton` | requires `aria-label` |
| `Chip` | editable chip for capture (click → popover editor); variants per field |
| `Badge` | HIGH/MED/LOW, NEW/MOVED/FLAG/HELD/AUTO/AI, counts |
| `MarkerAI` / `MarkerAuto` | tiny pills (AGT-7); tooltip shows token name + timestamp |
| `Duration` | renders `1h 45m` from minutes; `compact` → `1h45` |
| `Time` | renders HH:MM in settings tz |
| `Card`, `Section`, `Stat` | stat tiles of Today/Insights |
| `Sheet` | Radix Dialog; `side="right"` desktop / `"bottom"` mobile; drag-to-dismiss on mobile |
| `Drawer` | right panel inside layout (task detail) |
| `Popover`, `DropdownMenu`, `ContextMenu` | Radix; right-click on web = mobile long-press alternative |
| `Switch`, `Checkbox`, `Select`, `Combobox`, `NumberStepper`, `TimeInput`, `DateInput` | form controls; `TimeInput` HH:MM 24h, steps of slot granularity |
| `SegmentedProgress` | subtasks bar (TSK-8): one segment per subtask, width ∝ weight, filled if done |
| `StreakDots` | last N occurrences: full / compressed / skipped / missed / gap |
| `Toast` (sonner) | `toastUndo(label, token)` helper (§5) |
| `ConfirmDialog` | the 2 hard confirms; states the consequence text from the API |
| `EmptyState`, `Skeleton`, `ErrorState` (retry button) | |
| `Kbd` | shortcut hints |
| `LongPress` | wrapper: pointer down 450 ms → alternative action + haptic (`navigator.vibrate(10)`), cancels on move > 8 px; on desktop maps to context-menu |

## 3. App shell

### 3.1 Routes (Next.js App Router, `web/src/app/`)
Folders map 1:1 to the paths below: `(auth)/login/page.tsx`, `(app)/layout.tsx` (auth guard +
shell + providers), `(app)/today/page.tsx`, `(app)/tasks/[id]/page.tsx`,
`(app)/settings/[section]/page.tsx`, and so on. Every `page.tsx` is a thin client component
that renders `features/<name>`. The auth guard calls `GET /api/auth/me` client-side and redirects
to `/login?next=` on 401 (no server-side cookie reading needed).
```
/login                      WEB-05
/onboarding                 WEB-27 (first run; redirect here until Google connected & settings confirmed)
/                           → /today
/today                      WEB-10
/week?from=                 WEB-11 (desktop grid) / WEB-12 (mobile agenda)
/tasks?tab=&filter=         WEB-13
/tasks/:id                  task detail drawer over /tasks (WEB-15); direct link works
/tasks/import/:batchId      review import WEB-16
/habits                     WEB-17      /habits/:id  editor sheet
/prayers                    WEB-19
/decisions                  WEB-21
/log                        WEB-22
/insights                   WEB-23
/settings/:section          WEB-24 (google, precedence, calendars, working-hours, block-rules,
                            prayers, habit-defaults, task-defaults, vocab, notifications, backup,
                            agent, account, audit)
Global overlays (query-param driven so they deep-link): ?review=1 (review mode on the calendar, WEB-20),
?capture=1 (capture sheet WEB-14), ?palette=1 (⌘K)
```
Code splitting is automatic per route; use `next/dynamic` for heavy widgets (Recharts, dnd-kit grid).

### 3.2 Desktop shell (≥ 768 px) — `layout/DesktopShell.tsx`
```
┌──────────┬──────────────────────────────────────────────┬───────────────┐
│ Rail 208 │ Header 52: title · subtitle · view switch ·    │ Context panel │
│  ◈ Tartib│          ⇄ Re-plan (n) · + Capture (⌘N)        │ 320 (optional │
│  PLAN    ├──────────────────────────────────────────────┤ per screen)   │
│  Today   │ Main content (scrolls)                        │               │
│  Week    │                                               │               │
│  Tasks n │                                               │               │
│  Habits  │                                               │               │
│  ANCHOR  │                                               │               │
│  Prayers │                                               │               │
│  Insights│                                               │               │
│  Log     │                                               │               │
│  Decis. n│                                               │               │
│  Settings│                                               │               │
│ ──────── │                                               │               │
│ PRECED.  │                                               │               │
│ ● Meet.. │                                               │               │
│ (edit)   │                                               │               │
└──────────┴──────────────────────────────────────────────┴───────────────┘
```
- Rail collapses to 56 px icons at < 1100 px.
- Precedence list (FR-2) at the rail bottom, from `GET /api/settings` precedence order, each with
  its colour swatch; ranks relevant to the current screen are highlighted (e.g. Tasks screen
  highlights Tasks); "edit" links to `/settings/precedence`.
- Header right: **⇄ Re-plan badge** shows `ask_count` of the proposed run (from `/api/today.plan`
  kept fresh by the live-version hook, WEB-28). Click → `?review=1`. If no
  proposal, click runs `POST /api/plan/run` then opens review mode.
- Global shortcuts: `⌘K` palette · `⌘N`/`c` capture · `⌘R`/`r` review plan · `g t` today ·
  `g w` week · `g k` tasks · `g h` habits · `g p` prayers · `?` shortcuts help.

### 3.3 Mobile shell (< 768 px) — `layout/MobileShell.tsx`
- Top: large title (28 px) + subtitle + right pill (streak ◆14 / ⇄ n / filter) as in mockup mobile/01.
- Bottom tab bar (5): **Today · Week · Tasks · Habits · Prayer**; safe-area insets.
- Floating **+** capture button (gold, 56 px) on Today/Week/Tasks, bottom-right above tab bar.
- Insights, Log, Decisions, Settings via the avatar menu (top-left) → sheet with links; Decisions
  also via a red badge on the Today header when count > 0.
- Sheets are bottom sheets with snap points (50 % / 92 %).

## 4. Data layer

### WEB-04 details — API client (`src/api/`)
- `schema.d.ts` generated by `make gen-api` (never edit by hand).
- `client.ts`: `openapi-fetch` `createClient<paths>({ baseUrl: "/" })` with middleware: adds
  `X-Requested-With: tartib`, `Idempotency-Key` (uuid v4) on mutations, parses error JSON into
  `ApiError {status, code, message, details}`; 401 → redirect to `/login?next=`.
- `keys.ts`: query key factory: `qk.today()`, `qk.week(from)`, `qk.tasks(filters)`, `qk.task(id)`,
  `qk.habits()`, `qk.prayers(date)`, `qk.plan()`, `qk.log(filters)`, `qk.settings()`, `qk.decisions()`, …
- `hooks/*.ts`: one file per feature exporting `useX()` queries and `useXMutation()` mutations.
  Mutations: optimistic update where the result is predictable (tick habit, toggle subtask,
  progress), then `invalidateQueries` for `today`, `week`, `plan` and the entity. Every mutation
  response with `undo` → `toastUndo`.
- QueryClient defaults: `staleTime 30s`, `refetchOnWindowFocus true`, `retry` 1 for queries, 0 for mutations.

### Time (`src/lib/time.ts`)
- Read `settings.general.timezone` once (from `/api/auth/me` bootstrap or settings) and store in a
  Zustand `useTz()`; **all** formatting and "today" calculation use `TZDate` in that tz
  (FR-6: regardless of device tz). Helpers: `fmtTime`, `fmtDay` (`Sat 22`), `fmtRange`,
  `fmtDuration`, `minutesBetween`, `isToday`, `startOfWeek(from, weekStartsOn)`.
- Unit tests run with `TZ=America/New_York` to prove device tz is ignored.

## 5. Undo (`src/lib/undo.ts`)
```ts
toastUndo(label: string, undo: {token: string, expires_at: string}, onUndone?: () => void)
// sonner toast, duration 10_000, action "Undo" → POST /api/undo/{token} → invalidate → toast "Undone"
```
Keyboard: `⌘Z` triggers the most recent undo within its window.

## 6. Offline & PWA (NFR-8)

### WEB-08 — PWA shell
- **Serwist** (`@serwist/next`, SW source `src/app/sw.ts`, disabled in `next dev`). Manifest in
  `src/app/manifest.ts`: name "Tartib", short "Tartib", `display: standalone`, theme `#0b0d12`,
  icons 192/512 + maskable, `start_url: /today`.
- Precache app shell. Runtime caching: `GET /api/today|week|tasks|habits|prayers|settings` →
  **NetworkFirst** (timeout 3 s) so the cached read-only view works offline.
- An "Offline — showing saved view" banner when `navigator.onLine === false` or a fetch fell back to cache.

### WEB-09 — Write outbox
- Mutations made offline are stored in IndexedDB (`idb-keyval`) as
  `{id, method, path, body, idempotency_key, created_at, label}` and shown as pending chips
  ("2 changes waiting to sync").
- Replay on `online` event and on app start, in order, with the stored `Idempotency-Key`
  (server dedupes). 4xx → drop + error toast naming the action; 5xx/network → keep, back off.
- Only these actions may queue offline (safe and commutative): habit log/tick, habit skip
  (today), task progress, task create (manual form), subtask toggle, prayer prayed. Everything
  else is disabled offline with a tooltip "Needs a connection".
- Background Sync API where supported (`sync` event in SW) as a bonus; not required.

### WEB-26 — Push (in 08-web-screens, depends on IN-10)

## 7. Foundation work packages

### WEB-01 — Tokens, fonts, theme
**Depends on:** F-03 **Size:** S
**Files:** `design/tokens.css`, `design/blockStyles.ts`, `app/layout.tsx` (Inter + JetBrains Mono
via `next/font/google`, exposed as CSS variables), `lib/theme.ts` (system/dark/light, stored in
localStorage, applied before paint by a tiny inline script in the root layout to avoid a flash).
**Done when:** a `/__design` dev-only route renders swatches, type scale and block styles in both themes.

### WEB-02 — Component library
**Depends on:** WEB-01 **Size:** L
**Files:** `design/components/*` per §2, `design/components/index.ts`
**Tests:** Button loading disables; Sheet closes on Esc and returns focus; LongPress fires after
450 ms and not on scroll; Chip edits value via keyboard; SegmentedProgress widths.
**Done when:** `/__design` shows every component in every state.

### WEB-03 — Shells, navigation, precedence rail, shortcuts
**Depends on:** WEB-02, WEB-04 **Size:** M
**Files:** `shell/{DesktopShell,MobileShell,Rail,TabBar,Header,PrecedenceRail}.tsx`,
`shell/useBreakpoint.ts`, `shell/shortcuts.ts`, `app/(app)/layout.tsx`
**Tests:** at 390 px the tab bar renders and the rail doesn't; at 1280 px the reverse; `g t`
navigates; precedence order follows the settings payload.

### WEB-04 — API client & hooks scaffold
**Depends on:** F-03, BE-01 (OpenAPI available) **Size:** M
**Files:** `api/client.ts`, `api/keys.ts`, `api/errors.ts`, `api/hooks/` (start with `useMe`, `useSettings`), `lib/time.ts`, `lib/undo.ts`
**Tests:** MSW-mocked 401 redirects; error parsing; time helpers with a foreign device tz.

### WEB-05 — Auth screens
**Depends on:** WEB-04, BE-03, BE-04 **Size:** S
`/login`: email field → "Send magic link" → "Check your inbox" state; "Sign in with passkey"
button (`@simplewebauthn/browser`). After first login, a dismissible card on Today offers
"Add a passkey to this device". Session list in Settings → Account.

### WEB-06 — Command palette
**Depends on:** WEB-03 **Size:** M
**Spec:** mockup web/04 (⌘K does everything)
`cmdk` dialog. Sources: navigation, actions (capture "…", review plan, run plan), habits ("skip
gym" → Skip Gym today ↵ / until tomorrow ⌥↵ / until end of week), tasks (open, mark done, defer
to tomorrow), prayers (mark prayed, move Dhuhr inside window). Typing text that looks like a task
("2h DBMS before fri") shows "+ Add task “…”" as the first item (⌘N) → opens capture prefilled.
**Tests:** "skip gym" lists the three skip variants; Enter runs skip and shows undo toast.

### WEB-07 — Error boundaries, toasts, offline banner, 404
**Depends on:** WEB-03 **Size:** S

### WEB-28 — Live refresh (D-29)
**Depends on:** WEB-04, BE-27 **Size:** S
**Files:** `api/useLiveVersion.ts`, mounted once in `app/(app)/layout.tsx`
Poll `GET /api/version` every 5 s while `document.visibilityState === "visible"`, every 1 s for
20 s after any mutation settles, and immediately on focus or `online`. When `data_version`
changes, invalidate `today`, `week`, `plan`, `tasks`, `habits`, `prayers`, `decisions`. When
`ask_count` goes 0 → n, pulse the ⇄ badge. Stop polling when hidden.
**Tests:** fake timers: version change → invalidations; hidden tab → no requests.

### WEB-08 — PWA shell · WEB-09 — Outbox  (see §6)
**Depends on:** WEB-07 **Size:** M each
**Tests:** Playwright offline mode: Today renders from cache; tick habit offline → pending chip →
back online → synced once (server receives one request thanks to the idempotency key).
