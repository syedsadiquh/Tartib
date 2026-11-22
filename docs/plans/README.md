# Build Plans — Index & How To Use

These plans turn `docs/01-requirements.md` and `docs/02-engine-spec.md` into **small,
ordered work packages** that a coding model can run one at a time without needing the whole
picture. Each package names the files to touch, the steps, and how to check it is done.

> **Order of authority** (highest first):
> 1. `docs/01-requirements.md` and `docs/02-engine-spec.md` — product rules
> 2. `docs/decisions.md` — how ambiguities are resolved
> 3. These plans — how to build it
> 4. Mockups — visual intent only (the plans' UI specs replace them where they differ)

---

## Files

| File | What it covers | Work-package prefix |
|---|---|---|
| [00-roadmap.md](00-roadmap.md) | Milestones, dependency graph, the order to run packages in | — |
| [01-architecture.md](01-architecture.md) | Stack, repo layout, conventions, env vars, coding rules | `F-` |
| [02-data-model.md](02-data-model.md) | Every table, column, enum, constraint, index, and the seed data | `DB-` |
| [03-engine.md](03-engine.md) | The scheduling engine: types, algorithms, pseudocode, test cases | `EN-` |
| [04-backend-api.md](04-backend-api.md) | Services and every HTTP endpoint with request/response shapes | `BE-` |
| [05-integrations.md](05-integrations.md) | Google OAuth + Calendar sync, prayer times, Notion, push, LLM, email | `IN-` |
| [06-worker-and-jobs.md](06-worker-and-jobs.md) | Worker process, job queue, schedules, notifications, watchdog | `WK-` |
| [07-web-foundation.md](07-web-foundation.md) | Design system, app shell, API client, offline, PWA | `WEB-0x` |
| [08-web-screens.md](08-web-screens.md) | Every screen: layout, data, interactions, desktop + mobile | `WEB-1x/2x` |
| [09-deployment.md](09-deployment.md) | Docker, Caddy, VPS bootstrap, backups, monitoring, runbooks | `DP-` |
| [10-discord-bot.md](10-discord-bot.md) | Optional ~80-line Discord shim | `BOT-` |
| [11-testing.md](11-testing.md) | Test strategy, acceptance A1–A10 mapping, fixtures, CI gates | `T-` |
| [12-versioning.md](12-versioning.md) | SemVer rules, milestone → version map, Conventional Commits, release-please | `F-06/07` |

---

## How an implementing agent must work (read this every session)

1. **Read `/AGENTS.md`** at the repo root. It has the non-negotiable coding rules.
2. Open `00-roadmap.md` and pick the **first unchecked package whose dependencies are all
   checked**.
3. Read that package's section **in full**, plus every requirement ID it cites (e.g. `PRY-3`
   → `docs/01-requirements.md` §7).
4. Do **only** that package. Do not "also quickly" build the next one.
5. Write the tests the package lists **before or with** the code. A package is not done until
   its tests pass and `make check` is green.
6. Tick the package in `00-roadmap.md` (`- [x]`) and add a one-line note of anything
   surprising under the package's "Notes" bullet in the same roadmap line.
7. If the plan is wrong or ambiguous: **do not improvise.** Add a `PROPOSED` entry to
   `docs/decisions.md`, choose the most conservative option, and say so in the notes.

### Package template (every package in these plans follows it)

```
### XX-NN — Title
**Depends on:** XX-NN, …        **Size:** S (≤2h) | M (½ day) | L (1 day)
**Spec:** requirement IDs this implements
**Files:** paths created or changed
**Steps:** numbered, concrete
**Tests:** what to write; file paths
**Done when:** checklist the reviewer will verify
```

---

## Glossary of names used across all plans (do not rename)

| Name | Meaning |
|---|---|
| `IST` | `zoneinfo.ZoneInfo("Asia/Kolkata")` — but always read the tz from settings, never hard-code |
| *actor* | string: `user`, `agent:<token-name>`, `engine`, `system` |
| *placement* | one calendar block owned by the app (task chunk, habit occurrence, prayer, qada) |
| *literal* | fixed-time item: meeting, prayer, pinned block |
| *plan run* | one execution of the engine that produces a diff (`plan_run` row) |
| *change* | one item of a diff: `create` · `move` · `resize` · `delete` (flags travel separately in `plan_run.flags`) |
| *rule code* | `SCREAMING_SNAKE` identifier of the rule that caused a decision (see `03-engine.md` §3) |
| *what-if* | an engine dry run on a modified copy of the input, used for previews |
