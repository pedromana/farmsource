# Farmsource Session Handoff

Use this file as the first context file when opening Farmsource from VS Code Codex.

## Current Goal

Farmsource development has moved off the local Windows stack and onto the remote Linux dev environment. Local Windows should only need Git, SSH, and the IDE. The remote production install must stay separate from remote dev.

## Git State

- GitHub repo: `https://github.com/pedromana/farmsource`
- Primary branch currently used by the repo: `master`
- Latest pushed commit at handoff: `90d249c`
- Local and remote dev were clean and aligned with `origin/master` after the last setup.

Recent pushed commits:

- `75265d5` Prepare remote dev workflow
- `d74d939` Add migrations and backup operations
- `90d249c` Mark database scripts executable

## Server Layout

Production installation:

- Path: `/opt/farmsource`
- Purpose: production installation
- Status at handoff: intentionally left untouched
- App bind: `127.0.0.1:8010`
- Containers seen: `farmsource-web-1`, `farmsource-db-1`

Development installation:

- Path: `~/src/farmsource`
- Purpose: daily development
- SSH alias on Windows: `farmsource-dev`
- SSH target: `pmana@5.78.99.135`
- Compose project: `farmsource-dev`
- App bind: `127.0.0.1:8011`
- Containers seen: `farmsource-dev-web-1`, `farmsource-dev-db-1`

Do not overwrite `/opt/farmsource` while working on dev.

## Connect From Windows

Start an SSH tunnel:

```powershell
ssh -L 8011:127.0.0.1:8011 farmsource-dev
```

Open the dev app:

```text
http://127.0.0.1:8011
```

Open the remote repo in VS Code Remote SSH:

```text
~/src/farmsource
```

## Daily Remote Dev Commands

```bash
cd ~/src/farmsource
git status
git pull --ff-only
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web pytest
```

Run migrations:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic upgrade head
```

Seed demo data:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python seed_demo.py
```

Stop dev:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down
```

Reset dev Postgres only:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down -v
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python seed_demo.py
```

## Validation Done

At handoff:

- Local Windows tests passed: `43 passed`
- Remote dev tests passed: `43 passed`
- Remote dev Postgres was created through Alembic migration
- Remote dev app endpoints returned `200` for:
  - `/`
  - `/health`
  - `/customer/catalog`
  - `/customer/cart`
  - `/customer/orders`
  - `/static/manifest.json`
  - `/static/js/service-worker.js`
- Backup script smoke test passed

## Important Files

- `REMOTE_DEV_SETUP.md`: remote development setup and troubleshooting
- `PRODUCTION_OPERATIONS.md`: Alembic, backup, restore, production cutover notes
- `.env.remote.example`: non-secret remote dev environment template
- `docker-compose.yml`: base app service
- `docker-compose.production.yml`: Postgres Compose override
- `alembic.ini`, `migrations/`: migration setup
- `scripts/backup_postgres.sh`: Postgres backup helper
- `scripts/restore_postgres.sh`: Postgres restore helper

## Current Architecture

- Backend: FastAPI
- Server: Uvicorn for local dev, Gunicorn/Uvicorn worker in Docker
- Templates/static/PWA: Jinja templates plus `app/static`
- PWA files: `app/static/manifest.json`, `app/static/js/service-worker.js`
- Database: SQLAlchemy
- Local default DB: SQLite
- Remote dev DB: Dockerized Postgres
- Migrations: Alembic
- Node usage: Capacitor mobile wrapper tooling only

## Known Operational Notes

- `.env` files are ignored and must stay uncommitted.
- Remote dev uses `WEB_CONCURRENCY=1` to behave like local development and avoid concurrent seed races.
- `/opt/farmsource` is the future production checkout and was not updated during dev setup.
- The server password was shared during setup; rotate it and switch to SSH key auth.
- Before production payments, add Stripe webhook signature verification.
- Before promoting production, back up `/opt/farmsource` Postgres and plan migration/stamp carefully.

## Suggested Next Codex Prompt

```text
Read SESSION_HANDOFF.md, REMOTE_DEV_SETUP.md, and PRODUCTION_OPERATIONS.md. Continue Farmsource work from the remote dev environment at ~/src/farmsource. Do not modify /opt/farmsource unless explicitly asked.
```
