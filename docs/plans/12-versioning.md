# 12 — Versioning & Releases

Tartib uses **Semantic Versioning 2.0.0**: `vMAJOR.MINOR.PATCH` (e.g. `v0.4.2`). There is **one
version for the whole repo**. The backend, web app and bot always ship and are tagged together.

---

## 1. Increment rules

### Before 1.0 (`0.y.z` — initial development, the current phase)

| Change | Bump | Example |
|---|---|---|
| A roadmap milestone is completed (a new user-visible capability) | **MINOR** | `0.3.0 → 0.4.0` |
| Bug fix, docs, tests, refactor, dependency update | **PATCH** | `0.4.0 → 0.4.1` |
| Breaking change (API, DTO, DB needing a manual step) | **MINOR**, flagged `BREAKING` in the changelog | `0.4.1 → 0.5.0` |

In 0.x anything may change, but every breaking change must still be called out.

### From 1.0 (`1.y.z` and later)

| Change | Bump | Examples |
|---|---|---|
| **Incompatible** change | **MAJOR** | removing or renaming an endpoint, DTO field, rule code or enum value; an agent-token client would break; a migration that needs manual steps or data loss; changing a default rule that alters existing plans (e.g. precedence semantics) |
| **Backward-compatible** feature | **MINOR** | new endpoint, new optional DTO field, new screen, new setting with a default that keeps current behaviour |
| **Backward-compatible** fix | **PATCH** | bug fix, performance, security fix, copy change, dependency patch |

MINOR resets PATCH to 0, and MAJOR resets both (`1.4.3 → 2.0.0`).

### Pre-releases
Allowed only right before a release that needs real-calendar soak testing:
`v1.0.0-rc.1`, `v1.0.0-rc.2`, … → `v1.0.0`. Never deploy an `-rc` to the production VPS for
longer than the soak period.

### What counts as the public API (decides MAJOR after 1.0)
1. The HTTP API under `/api` (paths, request/response fields, error codes): agents depend on it.
2. Engine rule codes and enum values that appear in the API and the engine log.
3. Settings export/import JSON format (SET-16) and the Notion mirror layout (restores depend on it).
4. Database schema **only** where an upgrade needs manual work; ordinary Alembic migrations that run
   automatically don't count.

## 2. Milestone → version map

| Release | When |
|---|---|
| *(untagged)* | Design docs and plans (now) |
| `v0.1.0` | M0 Foundation done |
| `v0.2.0` | M1 Data |
| `v0.3.0` | M2 Engine |
| `v0.4.0` | M3 Backend core (fake Google) |
| `v0.5.0` | M4 Worker |
| `v0.6.0` | M5 Real Google |
| `v0.7.0` | M6 Web foundation |
| `v0.8.0` | M7 Web core screens: **first version usable day-to-day** |
| `v0.9.0` | M8 Agents & capture |
| `v0.10.0` | M9 Notifications & PWA |
| `v0.11.0` | M10 Backup, insights, recurrence |
| `v1.0.0-rc.N` | M11 deployed; at least 7 days of real use with no open P1 bugs |
| **`v1.0.0`** | M11 manual verification checklist (11-testing.md §4) fully green |
| `v1.1.0` | M12 Discord bot (optional) |

Patch releases (`v0.8.1`, …) ship whenever fixes land between milestones.

## 3. Commits → versions (automated)

Commits follow **Conventional Commits**, with the work-package ID as the scope:

```
feat(EN-05): prayer placement, shifting and qada stacking
fix(BE-14): roll back created events when the second patch fails
docs(plans): clarify D-24 overflow
test(EN-15): property test for idempotence
chore(deps): bump fastapi to 0.166
feat(BE-07)!: rename task.est_min to task.estimate_min        ← "!" = breaking
```
Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`, `revert`.
A breaking change uses `!` after the scope **and** a `BREAKING CHANGE:` footer explaining the
migration.

**release-please** (GitHub Action) reads these commits and keeps an open "Release PR" with
the next version and the generated `CHANGELOG.md`. Merging that PR creates the git tag
`vX.Y.Z` and a GitHub Release. Configuration (`release-please-config.json`):

```json
{
  "release-type": "simple",
  "include-v-in-tag": true,
  "bump-minor-pre-major": true,
  "bump-patch-for-minor-pre-major": true,
  "packages": { ".": {
    "extra-files": [
      { "type": "toml", "path": "backend/pyproject.toml", "jsonpath": "$.project.version" },
      { "type": "json", "path": "web/package.json", "jsonpath": "$.version" },
      { "type": "toml", "path": "bot/pyproject.toml", "jsonpath": "$.project.version" }
    ]
  } }
}
```
`.release-please-manifest.json` starts at `{".": "0.0.0"}`.

- `bump-patch-for-minor-pre-major: true`: during 0.x, individual `feat` commits only bump PATCH.
  The **MINOR bump for a completed milestone is done deliberately**: when the last package of a
  milestone merges, add an empty commit `chore(release): M2 complete` with the footer
  `Release-As: 0.3.0`. This keeps the milestone map in §2 exact.
- `bump-minor-pre-major: true`: during 0.x a breaking change bumps MINOR, not MAJOR.
- From 1.0, the normal rules apply automatically (`feat` → MINOR, `fix` → PATCH, `!` → MAJOR).

## 4. Where the version shows up

- `backend/pyproject.toml` `version`, `web/package.json` `version`, `bot/pyproject.toml`: kept
  identical by release-please. Never edit them by hand.
- `GET /api/health` → `{"status": "ok", "app_version": "0.8.1", "git_sha": "…"}`.
  (`GET /api/version` is the **data** version for live refresh, D-29, which is a different thing.)
- Web: Settings → Account footer shows "Tartib v0.8.1 · API v0.8.1". If the web and API
  **major.minor** differ (e.g. a Vercel deploy ahead of the VPS), show a small "Update in
  progress — reload soon" banner.
- Docker images are tagged `tartib-backend:0.8.1` and `:latest`. The deploy script records the
  version it deployed.
- Releases on GitHub carry the changelog. Deploy only from tags once at 0.8.0 or later (DP-06).

## 5. Work packages

### F-06 — Conventional Commits & release-please
**Depends on:** F-05 **Size:** S
**Files:** `.github/workflows/release-please.yml`, `release-please-config.json`,
`.release-please-manifest.json`, `CHANGELOG.md` (generated), `.github/workflows/commitlint.yml`
(or a commit-msg check in CI), `commitlint.config.js`
**Steps:**
1. Add the release-please workflow (on push to `main`) with the config in §3.
2. Lint PR titles and commits against Conventional Commits; the scope must be a package ID
   (`^[A-Z]+-\d+$`) or one of `plans|deps|release|repo`.
3. Set `version = "0.0.0"` in `backend/pyproject.toml` and `web/package.json` so release-please
   owns them from now on.
**Done when:** merging a `feat(F-06): …` PR produces a Release PR proposing `v0.0.1` with a
changelog entry; the milestone `Release-As` flow is documented in `docs/runbook.md`.

### F-07 — Version surfaces
**Depends on:** F-06, BE-01, WEB-03 **Size:** S
`GET /api/health` returns `app_version` (from package metadata) and `git_sha` (build arg
`GIT_SHA`); web reads `process.env.NEXT_PUBLIC_APP_VERSION` (set from `package.json` at build)
and shows the footer and the mismatch banner from §4.
**Tests:** health returns the pyproject version; the banner appears when major.minor differ (MSW).
