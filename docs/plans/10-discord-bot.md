# 10 — Optional Discord Bot Shim

**Spec:** NFR-11, `docs/04-deployment.md` §2 ("~80-line Python bot, ~60 MB, no browser, no LLM").
The bot is **just another agent client**: it holds an agent token (scopes `read`, `tasks.create`,
`tasks.edit` — auto-approve create/edit) and calls the public API. It must never touch the DB.

Habit skip and "tick" are user-only endpoints (AGT-3 forbids editing habits by agents). Decision:
the bot supports habit actions **only** by sending the user a deep link (`https://host/habits?skip=gym`),
keeping the AGT-3 boundary intact. *(If the owner wants one-tap Discord habit skips, that needs a
new scope and an entry in `docs/decisions.md` first.)*

### BOT-01 — Skeleton
**Depends on:** BE-21 **Size:** S
**Files:** `bot/pyproject.toml` (discord.py, httpx), `bot/sched_bot.py`, `deploy/bot.Dockerfile`, `.env.bot.example`
Env: `DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USER_ID` (only this user may command), `SCHED_API_URL`, `SCHED_AGENT_TOKEN`.

### BOT-02 — Commands
| Message | Action |
|---|---|
| `add 2h DBMS before fri` / `add <anything>` | `POST /api/capture/parse` → `POST /api/tasks` with the draft; reply with the parsed chips and gates ("saved to inbox — needs a calendar") |
| `next` / `what's next` | `GET /api/today` → current block + next 3 + next prayer |
| `today` | compact agenda |
| `done <task prefix>` | find task by title prefix (`GET /api/tasks?q=`) → `POST /api/tasks/{id}/state {done}` |
| `plan` | `GET /api/plan/current` summary + link to `/today?review=1` |
| `skip <habit>` | reply with deep link (see above) |
| `help` | list |
Ignore all messages from other users/channels (DM only). Reply errors in one line.

### BOT-03 — Packaging
Compose profile `bot` (09-deployment DP-02), `mem_limit: 96m`. Reconnect handled by discord.py.
**Tests:** parse command dispatcher with a fake API (httpx MockTransport).
