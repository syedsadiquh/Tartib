# Security policy

Tartib holds OAuth tokens for a real Google Calendar, so a flaw here can read or rewrite
someone's schedule. Please report privately — **never** in a public issue.

## Reporting

Use GitHub's [private vulnerability reporting](https://github.com/syedsadiquh/tartib/security/advisories/new).
Include what you did, what happened, and the version from the app footer or `/api/health`.

There is no bounty and no SLA. As a single-maintainer project, expect an answer when there is
one worth giving.

## In scope

- Token handling, encryption at rest (`APP_ENCRYPTION_KEY`), session or passkey bypass
- The calendar writer writing outside the calendars it owns, or outside the app's own events
- Any path that puts a secret in a log, an error response, or the engine log
- Injected or untrusted input reaching the scheduler, capture parser, or Notion mirror

## Out of scope

- Reports from automated scanners with no demonstrated impact
- Missing headers on a deployment that is not this repo's (see `docs/runbook.md`)
- Bugs that are merely wrong scheduling — those are ordinary issues
