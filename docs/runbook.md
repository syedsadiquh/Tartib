# Runbook — releases

Operational steps that are easy to get wrong. Architecture lives in `docs/plans/`;
this file is the "what do I type" version.

## Releases (F-06)

One version for the whole repo, tags `vX.Y.Z` (SemVer, `docs/plans/12-versioning.md`).
Nobody edits a version number by hand — `release-please` owns
`backend/pyproject.toml` and `web/package.json`.

### Normal flow

1. Merge work into `develop` (PRs target `develop`).
2. `release-please` runs on every push to **`main`**. It keeps a **"Release PR"** open
   titled `chore(main): release tartib X.Y.Z`, containing the version bump and the
   `CHANGELOG.md` entry built from the Conventional Commit subjects since the last tag.
3. Review that PR (the changelog is the release note) and merge it to `main`.
4. Merging it creates the tag `vX.Y.Z`, the GitHub Release, and the version bumps.

### Milestone releases (`Release-As`)

During `0.x`, individual `feat` commits only bump **PATCH**
(`bump-patch-for-minor-pre-major`). A completed roadmap milestone must land on the
exact version in the map (`v0.1.0` for M0, `v0.2.0` for M1, …), so the MINOR bump is
requested explicitly — **as the last commit merged for that milestone**:

```bash
git switch develop
git commit --allow-empty -m "chore(release): M0 complete" -m "Release-As: 0.1.0"
git push origin develop
```

Then follow the normal flow: `develop` → `main`, and the Release PR now proposes
`v0.1.0` instead of `v0.1.1`.

Rules that bite:

- `Release-As:` is a **footer**, so it goes in the second `-m` (after a blank line),
  not in the subject.
- The milestone number must match `12-versioning.md` §2. If a package slipped, fix the
  roadmap first — the tag is public and permanent.
- The commit must be on `main` before the Release PR is merged; a `Release-As` commit
  sitting on a feature branch does nothing.
- Never `git tag` by hand. Two taggers means a changelog that lies.

### Hotfix between milestones

Ordinary `fix(...)` commits bump PATCH (`v0.8.0` → `v0.8.1`). No `Release-As` needed.

### Pre-releases (`v1.0.0-rc.N`)

Before `v1.0.0` only, and only for soak testing on the real calendar: release-please
produces them when the manifest holds `1.0.0-rc.N`. Do not leave an `-rc` deployed on
the VPS past the soak window.

## Where the version appears

- `GET /api/health` → `app_version` and `git_sha` (F-07).
- Settings → Account footer: `Tartib vX.Y.Z · API vX.Y.Z`, plus an "update in
  progress" banner when web and API **major.minor** differ (F-07).
- Docker images tagged `tartib-backend:X.Y.Z` (DP-01/DP-06).
