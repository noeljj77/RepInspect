# Deployment

The production setup is `docker-compose.prod.yml`: three containers on one host.

| Service | What it is |
|---|---|
| `db` | PostgreSQL 17. Not published to the host; only the backend can reach it. |
| `backend` | FastAPI on Python 3.11 slim with CPU-only PyTorch. Runs `alembic upgrade head`, then one uvicorn process. |
| `web` | nginx. Serves the built React app, forwards `/api` to the backend, sets security headers. The only published port (`WEB_PORT`, default 8080). |

Volumes: `pgdata` (database), `artifacts` (imported source snapshots and search indexes) and
`models` (the embedding model, downloaded on first use, about 130 MB).

## First start

```bash
cp .env.example .env
```

Fill in `.env`:

- `POSTGRES_PASSWORD`: any long random string.
- `JWT_SECRET`: at least 32 characters. `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- Optionally `GITHUB_TOKEN` (higher GitHub rate limit) and `GEMINI_API_KEY` (AI features).

Then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f backend
```

The backend refuses to start with a missing or placeholder `JWT_SECRET`. The first chat or
index build downloads the embedding model into the `models` volume.

## TLS

The container speaks plain HTTP. For a public site, put a TLS-terminating proxy in front of
`web` (Caddy, a cloud load balancer, Cloudflare Tunnel). The backend runs with
`APP_ENV=production`, which marks the session cookie `Secure` and sends HSTS, so the site must
be served over HTTPS (browsers also accept `http://localhost` for trying it out).

Rate limiting uses the client address that nginx sees. Behind another proxy that is the
proxy's address, so all visitors would share one per-IP allowance. Fix it by telling nginx to
trust the proxy (`set_real_ip_from <proxy address>;` and `real_ip_header X-Forwarded-For;` in
`frontend/nginx.conf`). The per-email limit works either way.

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run when the backend starts. Data stays on the volumes.

## Backups

```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U repinspect repinspect > backup.sql
```

Source snapshots in the `artifacts` volume can be rebuilt by refreshing a repository, so the
database dump is what matters.

## Limits of this setup

- One backend process: analysis jobs run in threads and login limits are counted in memory.
  Running several backend containers would need a job queue and a shared limiter store.
- Uploaded ZIPs are limited to 50 MB (`MAX_UPLOAD_BYTES`; nginx allows 55 MB).
- Repository text is sent to Gemini when AI features are used. Secrets found in files are
  redacted before storage, but do not import code you are not allowed to share with a
  third-party service. Set `LLM_PROVIDER=none` to turn AI off.
