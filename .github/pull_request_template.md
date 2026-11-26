<!--
Title: Conventional Commits, scope = the area, never the work-package ID,
e.g. feat(engine): prayer placement, shifting and qada stacking
-->

## What changed
<!-- The behaviour, not the diff. Two to four bullets. -->

## Package
<!-- Closes #N completes a work package. Part of #N is one slice of a bigger package.
     Repo chores with no package use the `no-issue` label instead. -->

## Checklist
- [ ] Only the chosen package changed — no drive-by refactors
- [ ] Tests ship with the code; `make check` is green locally
- [ ] The package is ticked in `docs/plans/00-roadmap.md` with a one-line note
- [ ] A contract changed only with its plan section and a `PROPOSED` entry in `docs/decisions.md`
