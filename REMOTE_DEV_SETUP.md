# Farmsource Remote Development Setup

This guide moves day-to-day Farmsource development to a remote Linux server. Your Windows machine only needs an SSH client and a remote IDE such as VS Code Remote SSH or PyCharm Remote Development.

Current remote dev setup:

- Server: `pmana@5.78.99.135`
- SSH alias on this Windows machine: `farmsource-dev`
- Remote repo path: `~/src/farmsource`
- Compose project: `farmsource-dev`
- Server bind: `127.0.0.1:8011`
- Windows browser URL through SSH tunnel: `http://127.0.0.1:8011`

## Current Project Shape

- Backend: FastAPI served by `uvicorn` for development or `gunicorn` with Uvicorn workers for long-running server use.
- Templates/static/PWA: Jinja templates in `app/templates`, static assets in `app/static`, PWA manifest at `app/static/manifest.json`, and service worker at `app/static/js/service-worker.js`.
- Mobile wrapper tooling: Capacitor scripts in `package.json`; Node is only needed when syncing or building Android/iOS wrappers.
- Database: SQLAlchemy using `DATABASE_URL`. Local default is SQLite at `data/farmsource.db`; remote development should use Postgres.
- Migrations: there is no Alembic setup yet. Tables are created on app startup through `init_db()`, with limited SQLite legacy schema helpers.
- Seed data: `python seed_demo.py` loads demo catalog, customer, order, driver, and route data. `python seed_demo.py --reset` is only for local/development/test SQLite databases.
- Production/deployment files: `Dockerfile`, `docker-compose.yml`, `docker-compose.production.yml`, `.env.production.example`, and Linux/systemd notes in `README.md`.

Environment variables used by the app:

```env
APP_ENV
DEBUG
LOG_LEVEL
DATABASE_URL
STRIPE_SECRET_KEY
STRIPE_PUBLISHABLE_KEY
APP_BASE_URL
SESSION_SECRET_KEY
SESSION_COOKIE_SECURE
ADMIN_DEFAULT_EMAIL
ADMIN_DEFAULT_PASSWORD
MARKETING_AI_PROVIDER
RATE_LIMIT_ENABLED
WEB_CONCURRENCY
APP_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

## Recommended Approach

Use Docker Compose on the Linux server for remote development.

Option A, direct Linux install with Python/Node/Postgres, is workable but puts more state on the host and makes dependency cleanup harder.

Option B, Docker Compose, is safer for Farmsource right now because the repo already has a Dockerfile, Compose support, and a Postgres override. It keeps Python dependencies, Postgres data, and app runtime isolated from the server OS.

Option C, hybrid, is useful later if you want the FastAPI process running directly under the IDE debugger while Postgres stays in Docker. For normal daily work, start with full Compose.

## One-Time Server Setup

Use this server:

```text
Host: 5.78.99.135
User: pmana
```

You can connect directly:

```bash
ssh pmana@5.78.99.135
```

Or add an SSH alias on Windows at `%USERPROFILE%\.ssh\config`:

```sshconfig
Host farmsource-dev
  HostName 5.78.99.135
  User pmana
```

Install baseline tools on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in so the Docker group membership is active, then verify:

```bash
docker --version
docker compose version
```

If `docker ps` still requires `sudo`, reconnect to SSH or reboot the server.

Create a clean project directory:

```bash
mkdir -p ~/src
cd ~/src
```

Clone the repository:

```bash
git clone https://github.com/pedromana/farmsource.git
cd farmsource
```

If the repo already exists on the server:

```bash
cd ~/src/farmsource
git status
git pull --ff-only
```

Create the remote development environment file:

```bash
cp .env.remote.example .env
python3 - <<'PY'
from pathlib import Path
from secrets import token_urlsafe

path = Path(".env")
text = path.read_text()
text = text.replace("replace-dev-postgres-password", token_urlsafe(24))
text = text.replace("replace-with-a-long-random-dev-secret", token_urlsafe(48))
path.write_text(text)
PY
```

Never commit `.env`. It is ignored by `.gitignore`.

## Start The Remote App

Build and start the app plus Postgres:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Initialize tables explicitly:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python -c "from app.database import init_db; init_db()"
```

Seed demo producer/catalog/order/route data:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python seed_demo.py
```

Check health:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
curl http://127.0.0.1:8011/health
```

## Connect From Windows

VS Code Remote SSH:

1. Install the "Remote - SSH" extension locally.
2. Connect to `farmsource-dev` or `pmana@5.78.99.135`.
3. Open folder `~/src/farmsource`.
4. Use the remote terminal for all commands.

PyCharm Remote Development:

1. Use `File > Remote Development > SSH`.
2. Connect to `farmsource-dev` or `pmana@5.78.99.135`.
3. Select `~/src/farmsource`.
4. Let PyCharm install its remote backend under your server home directory.

Keep the repository and dependency caches on the server. Do not clone into your Windows project directory for daily remote work, and do not sync `node_modules`, `.venv`, Docker volumes, or database files back to Windows.

## Access In Browser

The remote development Compose file binds the app to `127.0.0.1:8011` on the server. Use an SSH tunnel from Windows:

```powershell
ssh -L 8011:127.0.0.1:8011 farmsource-dev
```

Then open:

- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/customer/catalog`
- `http://127.0.0.1:8011/customer/cart`
- `http://127.0.0.1:8011/admin`
- `http://127.0.0.1:8011/driver`
- `http://127.0.0.1:8011/static/manifest.json`

## Daily Commands

Open the remote repo:

```bash
cd ~/src/farmsource
```

Pull latest changes:

```bash
git pull --ff-only
```

Start or restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Stop:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down
```

View logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.yml -f docker-compose.production.yml logs -f db
```

Run tests:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web pytest
```

Run the current table initialization:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python -c "from app.database import init_db; init_db()"
```

Run Alembic migrations:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic upgrade head
```

Seed demo data:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python seed_demo.py
```

Open a shell in the app container:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web sh
```

## Non-Docker Fallback

Use this only if Docker is unavailable on the server.

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git postgresql postgresql-contrib
cd ~/src/farmsource
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.remote.example .env
```

Set `DATABASE_URL` in `.env` to point at the host Postgres service, then run:

```bash
python -c "from app.database import init_db; init_db()"
python seed_demo.py
uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
```

## Validation Checklist

After startup, verify:

```bash
curl http://127.0.0.1:8011/health
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web pytest
```

Manual browser checks through the SSH tunnel:

- Customer catalog loads at `/customer/catalog`.
- Cart and checkout load at `/customer/cart` and `/customer/checkout`.
- Order lookup loads at `/customer/orders`.
- Admin login loads at `/admin/login`.
- Admin route pages load at `/admin/routes`.
- Driver login and route pages load at `/driver`.
- PWA manifest and service worker load from `/static/manifest.json` and `/static/js/service-worker.js`.

## Troubleshooting

Port already in use:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down
```

Or change `APP_PORT` in `.env`, for example:

```env
APP_PORT=127.0.0.1:8011
APP_BASE_URL=http://127.0.0.1:8011
```

Database connection errors:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml ps
docker compose -f docker-compose.yml -f docker-compose.production.yml logs db
docker compose -f docker-compose.yml -f docker-compose.production.yml logs web
```

Environment changes not taking effect:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d --force-recreate
```

Clean rebuild without deleting Postgres data:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml build --no-cache web
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

Delete the remote development Postgres volume only when you intentionally want a fresh database:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down -v
```

Disk usage checks:

```bash
df -h
docker system df
```

Clean unused Docker build cache and stopped containers:

```bash
docker system prune
```

Do not prune volumes unless you are prepared to delete the development database.

## Production Readiness Gap

Remote development is not production deployment. Before production, add Alembic migrations, use production-only secrets, configure HTTPS behind Nginx or another reverse proxy, enable real Stripe webhook verification, and create a database backup plan.
