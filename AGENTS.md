# AGENTS.md — Rules for coding agents working in this repo

You are building **Tartib**, a single-user scheduling app that writes to a real Google Calendar. A bug here
means a missed prayer or a silently dropped task. Be careful, be literal, and test everything.

## Start of every session
1. Read `docs/plans/README.md` (how to work) and `docs/plans/00-roadmap.md` (what's next).
2. Pick **one** package: the first unchecked one whose dependencies are all checked.
3. Read its section in full, plus every requirement ID it cites in `docs/01-requirements.md` /
   `docs/02-engine-spec.md`, plus related entries in `docs/decisions.md`.

## Non-negotiable rules
1. **Do only the chosen package.** No drive-by refactors, no "while I'm here".
2. **Never change a contract silently.** Table/column names, endpoint paths, DTO fields, rule
   codes and enum values are defined in the plans. If one must change, update the plan file
   in the same change and add a `PROPOSED` entry to `docs/decisions.md`.
3. **Ambiguity → stop and record.** Add a `PROPOSED` decision, pick the most conservative option
   (writes less, moves less, flags more), and note it in the roadmap line.
4. **The engine is pure** (`backend/src/scheduler/engine/`): stdlib only, no I/O, no
   `datetime.now()`, no randomness, deterministic ordering (sort with an id tiebreaker).
   `tests/test_architecture.py` enforces this — never weaken that test.
5. **No hard-coded scheduling numbers** (SET-0). Minutes, times, thresholds come from settings.
   Defaults live only in `backend/src/scheduler/seed/defaults.py`.
6. **Time:** tz-aware datetimes everywhere; local math uses the settings tz (default
   Asia/Kolkata); only `scheduler/clock.py` reads wall time.
7. **Nothing writes to Google Calendar except** these paths, all through
   `services/calendar_writer.py`: plan apply (`services/apply.py`, incl. its rollback), the user
   drag/pin in BE-15, and the user's prayer actions in BE-12 (mark prayed → truncate, move qada).
   Stray/orphan events are removed only via a reviewed `delete` change (IN-05).
8. **Attribution:** every mutating service takes `ActorContext` first and stamps `*_by` /
   `*_auto_approved`.
9. **Tests ship with the code.** A package is done only when its listed tests exist and pass and
   `make check` is green. Don't delete or skip failing tests to get green.
10. **Secrets:** never log or commit tokens, keys, `.env`. Use `services/secrets.py`.
11. **Generated files:** `web/src/api/schema.d.ts` is generated (`make gen-api`); never hand-edit.
12. **Out of scope** (requirements §3): meetings/booking, multi-user, AI prioritisation, native apps.
13. **The tracker is the only source of truth for "what is left".** One issue per work package,
    on the project board, with its milestone and `area:*` / `size:*` labels. Every PR names the
    package in its body — `Closes #N` when it completes one, `Part of #N` when it is a slice —
    which is what links it to the board. `.github/workflows/tracker.yml` copies the PR's area
    label from its title scope and its milestone from the issue, and fails a PR that links
    nothing unless it carries `no-issue` (repo chores only). Never add a PR as its own board
    item; the issue's "Linked pull requests" field is where PRs belong.

## Commands
```
make dev-db        # postgres (+ mailpit) for local dev
make migrate seed  # schema + defaults
make dev-api       # FastAPI on :8000   (FAKE_GOOGLE=1 for no Google)
make dev-worker    # APScheduler + queue
make dev-web       # Next.js on :3000 (rewrites /api → :8000)
make check         # lint + typecheck + all unit/service/api tests
make gen-api       # OpenAPI → web/src/api/schema.d.ts
make test-e2e      # Playwright against the compose stack
```

## Finishing a package
- Tick it in `docs/plans/00-roadmap.md` with a one-line note.
- Commit message: Conventional Commits with an **area** as the scope, never a work-package code —
  `feat(engine): prayer placement, shifting and qada stacking`, `fix(api): …`, `ci: …`.
  Areas: `engine`, `api`, `worker`, `web`, `db`, `deploy`, `bot`, `ci`, `docs`, `plans`,
  `release`, `deps`, `repo`. The package ID (`EN-05`) belongs in the PR body, the roadmap line
  and the decision log — it reads as an internal ticket in `git log` (D-39).
  Breaking change → `feat(engine)!: …` plus a `BREAKING CHANGE:` footer. Versions and the
  changelog are produced by release-please; never edit version numbers by hand
  (`docs/plans/12-versioning.md`).
- No AI attribution lines (`Co-Authored-By`, "Generated with …") in commits or PRs.
- Open the PR against `develop` with the template filled in: the title carries the area scope,
  the body carries `Closes #N` (or `Part of #N` for one slice of a larger package), and the
  tracker workflow then applies the `area:*` label and the issue's milestone. Move the issue to
  **In Progress** when the branch starts and to **Done** when the PR merges.

