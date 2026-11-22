# Tartib — Deployment & Hosting

How Tartib runs 24×7, what it needs, and how it stays isolated and backed up.

---

## 1. What runs where

| Component | Where | Required 24×7 | Memory |
|---|---|---|---|
| Next.js PWA | Vercel | yes (managed) | — |
| Caddy (TLS for the API host) | VPS | yes | ~30–50 MB |
| FastAPI API | VPS | yes | ~150–250 MB |
| Worker (APScheduler + job queue) | VPS | yes | ~120–200 MB |
| Postgres 19 | VPS | yes | ~150–300 MB |
| Discord bot shim | VPS | optional | ~60–90 MB |
| External agents | anywhere | no | — |

The core stack is idle almost all the time (≈ 0.2 vCPU average). Prayers, planning and calendar
sync never depend on any personal device being on.

## 2. Agents and the bot

Agents are **clients**, never part of the runtime. An agent talks to the API over HTTPS with a
scoped token (requirements §15A). The token controls what it may do, not where it runs. An agent
can run on any machine, and the app keeps working when no agent is running.

For quick commands from Discord ("add 2h revision before fri", "what's next"), a small bot shim
(`docs/plans/10-discord-bot.md`) runs on the VPS. It needs no browser and no AI, and it calls the
same API with its own token.

## 3. Hosting shape and isolation

One small VPS runs the whole backend under Docker Compose, with **hard memory caps** per
container (NFR-10):

```yaml
services:
  api:    { mem_limit: 384m, cpus: 1.0 }
  worker: { mem_limit: 256m, cpus: 0.5 }
  db:     { mem_limit: 320m }
  caddy:  { mem_limit: 48m }
```

If the same host runs other applications, give them their own compose projects, networks and
memory limits. A misbehaving co-tenant is then OOM-killed inside its own container and can
never interrupt prayer scheduling or a calendar write.

**Recommended size:** 2 vCPU / 4 GB RAM / 40 GB disk, ideally with daily snapshots included.
Pick a region close to you for UI latency; the scheduled jobs don't care where they run.
Plan around the **renewal** price, not the introductory one.

## 4. Hostnames and TLS

- Google OAuth won't accept a bare IP as a redirect URI, and PWAs and service workers need
  HTTPS, so self-signed certificates are not an option.
- **Web:** `tartib.vercel.app`. The OAuth callback and every browser request go through this
  host, and `/api/*` is rewritten to the VPS.
- **API:** a free **DuckDNS** hostname (`tartib-api.duckdns.org`) pointing at the VPS. Caddy
  obtains a Let's Encrypt certificate for it automatically. Google's push notifications
  (calendar changes) are delivered here.

## 5. Backups

1. **Provider snapshot** (daily, whole disk), where the VPS plan includes it.
2. **Notion mirror:** a write-only logical copy of tasks, habits (including streaks and
   occurrence history) and settings after every plan application. It is read only during a
   restore, which runs a dry-run diff first (NOT-1..4, SET-12).
3. **Optional nightly `pg_dump`** uploaded to Google Drive (`drive.file` scope), kept 14 days
   (NFR-5).

The snapshot covers "the disk died yesterday". The Notion mirror covers "I noticed a problem
three days later", which a single 24-hour snapshot can't.

## 6. Running cost

| Line | Monthly |
|---|---|
| VPS (2 vCPU / 4 GB) | ≈ $4–6 |
| Vercel Hobby | $0 |
| DuckDNS + Let's Encrypt | $0 |
| Backups (snapshot + Notion) | $0 |
| Healthchecks.io (free tier) | $0 |
| AI for natural-language capture (optional) | a few cents |
| **Total** | **≈ $5** |

Step-by-step setup: `docs/plans/09-deployment.md`.
