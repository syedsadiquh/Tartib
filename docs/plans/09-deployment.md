# 09 — Deployment & Operations

Target (from `docs/04-deployment.md`): **one small VPS** (OVH VPS-1 Singapore, 2 vCPU / 4 GB,
daily backup included), Docker Compose, Caddy TLS on a **DuckDNS** hostname, total scheduler
memory hard-capped at ~1 GB (NFR-10) so co-hosted test apps can't kill it.

---

### DP-01 — Dockerfiles
**Depends on:** F-02, F-03 **Size:** M
**Files:** `deploy/backend.Dockerfile`, `.dockerignore`
**backend.Dockerfile** (used by `api` and `worker`, different commands):
```dockerfile
FROM python:3.15-slim AS base          # Debian trixie base; verify the tag exists when building
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv \
 && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-19 \
 && rm -rf /var/lib/apt/lists/*      # pg_dump 19 for DP-07 (must match the server major version)
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
RUN useradd -u 10001 app && chown -R app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
# api:    uvicorn scheduler.api.app:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
# worker: python -m scheduler.worker
```
**No web image:** the web app is deployed to Vercel (DP-09). Caddy uses the stock
`caddy:2-alpine` image with the Caddyfile mounted.
Build context = repo root.

### DP-02 — Production compose with memory caps
**Depends on:** DP-01 **Size:** S
**Files:** `deploy/docker-compose.yml`
```yaml
name: tartib
services:
  db:
    image: postgres:19-alpine
    environment: { POSTGRES_DB: tartib, POSTGRES_USER: tartib, POSTGRES_PASSWORD: ${POSTGRES_PASSWORD} }
    command: ["postgres", "-c", "shared_buffers=64MB", "-c", "max_connections=30", "-c", "work_mem=4MB"]
    volumes: [ "pgdata:/var/lib/postgresql" ]   # PG 18+ images keep data in /var/lib/postgresql/<major>/docker
    healthcheck: { test: ["CMD-SHELL","pg_isready -U tartib"], interval: 10s, retries: 5 }
    mem_limit: 320m
    restart: unless-stopped
  api:
    build: { context: .., dockerfile: deploy/backend.Dockerfile }
    command: ["sh","-c","alembic upgrade head && uvicorn scheduler.api.app:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
    env_file: ../.env
    depends_on: { db: { condition: service_healthy } }
    mem_limit: 384m
    cpus: 1.0
    restart: unless-stopped
  worker:
    build: { context: .., dockerfile: deploy/backend.Dockerfile }
    command: ["python","-m","scheduler.worker"]
    env_file: ../.env
    depends_on: { db: { condition: service_healthy }, api: { condition: service_started } }
    mem_limit: 256m
    cpus: 0.5
    restart: unless-stopped
  caddy:
    image: caddy:2-alpine
    ports: [ "80:80", "443:443" ]
    environment: { API_HOST: ${API_HOST} }
    volumes: [ "./caddy/Caddyfile:/etc/caddy/Caddyfile:ro", "caddy_data:/data", "caddy_config:/config" ]
    depends_on: [ api ]
    mem_limit: 48m
    restart: unless-stopped
  bot:
    profiles: [ "bot" ]
    build: { context: .., dockerfile: deploy/bot.Dockerfile }
    env_file: ../.env.bot
    mem_limit: 96m
    restart: unless-stopped
volumes: { pgdata: {}, caddy_data: {}, caddy_config: {} }
```
Total ≈ 1.02 GB (bot optional). Only Caddy publishes ports. The worker waits for migrations by
retrying DB head-check for up to 60 s at startup.

### DP-03 — Caddyfile
**Files:** `deploy/caddy/Caddyfile`
```
{$API_HOST} {
  encode zstd gzip
  header {
    Strict-Transport-Security "max-age=31536000"
    X-Content-Type-Options nosniff
    -Server
  }
  handle /api/* { reverse_proxy api:8000 }
  handle { respond 404 }
}
```
The browser never talks to this host directly; Vercel's `/api` rewrite and Google's webhooks do.
Web security headers (CSP etc.) are set in `web/next.config.ts`.

### DP-04 — Secrets & `.env`
- `.env` on the server only (chmod 600, owned by deploy user); never committed. Generate with
  `deploy/scripts/gen-env.sh` (creates Fernet key, session secret, Postgres password; asks for
  `API_HOST`, `API_PUBLIC_URL`, `APP_BASE_URL` (the Vercel URL), `OWNER_EMAIL`).
- Everything else (Google client, Notion, LLM, Discord, Healthchecks URL) is entered in the
  app's Settings and stored encrypted (D-18).
- **Back up `APP_ENCRYPTION_KEY` in your password manager** — without it, stored tokens can't be
  decrypted after a restore (the app then asks to re-connect Google; nothing else is lost).

### DP-05 — VPS bootstrap runbook (`deploy/scripts/bootstrap-vps.sh` + `docs/runbook.md`)
1. Create VPS (Ubuntu 24.04). Add SSH key; disable password login; `ufw allow 22,80,443`.
2. Create user `deploy`, add to `docker` group. Install Docker Engine + compose plugin.
3. Swap 1 GB (`fallocate`), `vm.swappiness=10`.
4. DuckDNS: create `tartib-api.duckdns.org` (the **API host**) → VPS IPv4; cron on the box to refresh every 5 min
   (only needed if the IP can change).
5. `git clone` the repo to `/opt/tartib`, run `gen-env.sh`, then
   `docker compose --env-file .env -f deploy/docker-compose.yml up -d --build`.
6. `docker compose exec api scheduler-cli login-link` → open the link → onboarding.
7. Google Cloud Console: OAuth client (Web), authorised redirect
   `https://tartib.vercel.app/api/google/callback` (the **Vercel** host — the request reaches the
   API through the rewrite); publish the consent screen to **Production** (Testing
   mode refresh tokens expire after 7 days — the cause of the old `invalid_grant` failures).
   Paste client id/secret in Settings → Google → Connect.
8. Healthchecks.io: create a check (period 5 min, grace 5 min), integrate with Discord/email;
   paste ping URL in Settings → Backup/Monitoring.

### DP-06 — Deploy script
`deploy/scripts/deploy.sh` (run from laptop): `ssh deploy@host 'cd /opt/tartib && git pull --ff-only && docker compose --env-file .env -f deploy/docker-compose.yml up -d --build && docker image prune -f'`, then curl `/api/health/ready` until 200 (60 s) else print logs. Migrations run in the api container start command.
Optional later: GitHub Actions builds images to GHCR and the server only pulls (saves CPU on the box).

**Release-based deploys (from v0.8.0):** `deploy.sh <tag>` checks out an exact `vX.Y.Z` tag
instead of `main`, builds the images tagged with that version, and writes it to
`/opt/tartib/DEPLOYED_VERSION`. Rollback = `deploy.sh <previous tag>`. Vercel production deploys
are promoted from the same tag (Vercel "Promote to Production" on the tagged commit).

### DP-07 — Backups
1. **OVH daily snapshot** (included) — whole disk.
2. **Notion mirror** (IN-08) — logical, dated.
3. Optional `pg_dump` nightly (`backup.pg_dump_to_drive`): worker runs `pg_dump -Fc` (via
   `subprocess` with the DB URL) → upload via IN-14 (Google Drive, `drive.file` scope) → keep `retention_days` (default 14,
   NFR-5); record `backup_run`. Without IN-14, dumps stay in a `backups` volume (14 files) and
   leave the box only via the OVH snapshot.
4. Restore drill (DP-08) quarterly: restore to a scratch compose project from pg_dump and from Notion; record timings (NOT-4 ≤ 15 min).

### DP-08 — Runbook (`docs/runbook.md`)
Sections: deploy · roll back (`git checkout <prev> && up -d --build`) · rotate secrets ·
re-authorize Google · read logs (`docker compose logs -f worker`) · "box is dead" checklist ·
restore from Notion (Settings → Backup → Dry run → Apply) · restore from pg_dump
(`pg_restore -c -d …`) · what each alert means (watchdog warn/loud, apply rolled back, token revoked).

### DP-09 — Vercel deployment of the web app
**Depends on:** F-03, DP-03 **Size:** S
**Spec:** D-02
1. Import the GitHub repo into Vercel (Hobby). Root directory `web`, framework preset Next.js,
   install `pnpm install --frozen-lockfile`, build `pnpm build`.
2. Environment variable `API_ORIGIN=https://tartib-api.duckdns.org` (Production + Preview).
3. Production domain `https://tartib.vercel.app` → set `APP_BASE_URL` on the VPS to it (cookies,
   passkey RP id, OAuth redirect, links in emails/pushes all use it).
4. Preview deployments: they hit the same production API, so **disable** "Preview deployments"
   for safety, or point previews at a separate staging API.
5. Check after deploy: `https://tartib.vercel.app/api/health/ready` → 200 through the rewrite; log in;
   the PWA install prompt appears on the phone; a push notification arrives.
6. Note for the runbook: the web app can be re-deployed (git push) without touching the VPS, and
   vice versa. API changes that break the DTOs must ship API-first and be backward compatible
   for one deploy.

**Major upgrades of Postgres** (e.g. 19 → 20): the data directory is per major version, so use
`pg_upgrade` (the `pgautoupgrade` image or a dump/restore into a fresh volume), never just
bump the image tag. Take a `pg_dump` and a VPS snapshot first. Add this to the runbook (DP-08).
