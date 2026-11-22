# 11 — Testing Strategy & Acceptance Mapping

The engine decides what goes on a real calendar; a regression is a missed prayer or a silently
dropped task. So: **tests are written with the code, in the same package, and CI blocks merges.**

## 1. Layers

| Layer | Tooling | Location | DB? | Speed |
|---|---|---|---|---|
| Engine unit + acceptance + property | pytest, hypothesis | `backend/tests/engine/` | no | < 10 s |
| Services | pytest + real Postgres (`tartib_test`), transaction-per-test rollback | `backend/tests/services/` | yes | < 60 s |
| API | FastAPI `TestClient`, fake Google/Notion/push | `backend/tests/api/` | yes | < 60 s |
| Web unit/component | Vitest + Testing Library + MSW | `web/src/**/*.test.tsx` | — | < 30 s |
| E2E | Playwright (projects: `desktop-chromium` 1440×900, `mobile-webkit` 390×844) against `next build && next start` (API_ORIGIN → local API) + compose backend with `FAKE_GOOGLE=1` | `web/e2e/` | yes | minutes |
| Accessibility | `@axe-core/playwright` on every route in e2e | `web/e2e/a11y.spec.ts` | | |

### Fixtures
- `backend/tests/fixtures/engine_builders.py` — fluent builders (EN-02).
- `backend/tests/fixtures/factories.py` — DB factories: `make_task(session, **kw)`, `make_habit`,
  `make_calendar`, `make_meeting`, `connect_fake_google()`.
- `backend/tests/conftest.py` — `clock` fixture (frozen at `2026-11-27T09:00+05:30` — a Friday —
  unless overridden), `db_session`, `client` (authenticated as user), `agent_client(scopes, auto)`.
- `backend/tests/fixtures/parser_cases.json` — shared with the web parser (WEB-14).
- `web/e2e/seed.ts` — calls a **test-only** endpoint `POST /api/__test/seed/{scenario}` (mounted
  only when `APP_ENV=test`) to load named scenarios: `empty`, `typical_week`, `overload_thu`,
  `qada_day`, `agent_import`.

## 2. Acceptance scenarios (requirements §23) → tests

| ID | Scenario | Engine test (EN-15) | Service/API test | E2E |
|---|---|---|---|---|
| A1 | Dhuhr vs 13:00–13:15 meeting → 13:20 | `test_a1_prayer_shift` | log row "shifted, 10m edges kept" after apply | Prayers shows "moved 13:00 → 13:20" |
| A2 | Window fully booked → qada after Isha, dashed, task-proof | `test_a2_qada_after_isha` (+ invariant: no task overlaps) | DB exclusion constraint rejects overlapping task | Timeline renders dashed qada |
| A3 | Minimal shrink 3h → 2h15 | `test_a3_minimal_shrink` | log "gave 45m, not more" | — |
| A4 | Shrink to floor + 30m flag | `test_a4_floor_and_flag` | flag columns set on task | Decisions shows "30m short" |
| A5 | Skip habit frees 30m, flag clears | `test_a5_skip_then_free` (what-if) | skip → replan → flag NULL | skip from Decisions lever clears badge |
| A6 | 3 skipped weekly occurrences → ended | — | `test_a6_three_skips_weekly` (BE-11) | ended card + Reactivate |
| A7 | Skip-until on daily habit costs streak | — | `test_a7_skip_until_breaks` | preview text before confirm |
| A8 | Overload ignored → exactly one reminder | — | `test_a8_one_reminder` (WK-04) | — |
| A9 | Dragged block stays pinned | `test_a9_pinned_left_alone` | move API → pinned; next 3 plans don't touch | drag in Week → pin badge, re-plan doesn't move it |
| A10 | Notion restore reproduces state | — | `test_a10_restore_roundtrip` (IN-09, fake Notion) | — |

Also mandatory, from the goals:
- **G1** — property test: every eligible task ends in `placed | partial (flagged) | blocked (flag) | deferred`; nothing vanishes.
- **G2/CAL-4** — API test: apply writes every accepted change to the fake calendar before returning; e2e asserts fake calendar contents.
- **G5** — property test over random precedence-respecting inputs: no lower-ranked block overlaps a higher one.
- **ENG-4** — idempotence property.
- **RPL-5** — failure-injection matrix (IN-06, BE-14).
- **FR-7** — DB-level tests for the three invariants (DB-01).
- **SET-0** — "non-default settings are honoured" engine test + the no-magic-numbers lint.
- **AGT-3** — for every never-grantable route, a test asserting 403 for an agent with all scopes.
- **D-29** — latency test: an edit through the API reaches the fake Google calendar in < 10 s with
  the worker running; a fake push webhook leads to a re-plan in < 5 s.
- **D-15** — pin over a meeting → no flag; pin over prayer → `PINNED_CONFLICT`; past block logs minutes.
- **NFR-7** — perf tests: engine < 500 ms (CI), `/api/today` < 300 ms warm with `typical_week` seed.
- **FR-6** — web time tests under a foreign `TZ`; backend tests with the system tz set to UTC.

## 3. CI gates (F-05)
1. `ruff check`, `ruff format --check`, `mypy` (strict on engine), architecture test, no-magic-numbers.
2. Backend tests; coverage: `engine/` ≥ 95 %, `services/` ≥ 85 %, total ≥ 80 %.
3. Web: `tsc --noEmit`, eslint, vitest (coverage ≥ 70 % on `features/` and `lib/`).
4. OpenAPI drift check: regenerate `schema.d.ts` and fail if it differs from the committed file.
5. E2E + axe on `main` (and on PRs labelled `e2e`).

## 4. Manual verification checklist (before going live)
- [ ] Connect real Google; discovery lists all calendars; tick work calendar as meetings feed.
- [ ] First plan shows prayers for 14 days, nothing written until Apply.
- [ ] Apply; events appear in Google within 60 s with correct calendars/colours.
- [ ] Move an app event in Google → within 2 min the app shows it pinned.
- [ ] Add a meeting over Dhuhr in Google → re-plan proposes the shift.
- [ ] Kill the worker container → Healthchecks alert within ~10 min.
- [ ] Phone: install PWA, enable push, receive a prayer notification, tick a habit from the notification.
- [ ] Airplane mode: Today renders; tick habit queues; reconnect syncs once.
- [ ] Notion mirror populated; restore dry run shows "unchanged" for everything.
