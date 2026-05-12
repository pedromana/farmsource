# Farmsource

Farmsource is a v1 foundation for a local farm-to-consumer marketplace. The pilot is aimed at the Seattle region and is designed around scheduled delivery routes, not instant delivery.

This repository is intentionally small: it provides the FastAPI app, environment-based configuration, SQLite database setup, static files, basic page shells, Docker support, and deployment notes.

## What is included

- Customer-facing shell at `/customer`
- Admin dashboard shell at `/admin`
- Driver mobile-friendly shell at `/driver`
- Landing page at `/`
- Health check at `/health`
- SQLAlchemy setup using `DATABASE_URL`
- SQLite local default with an easy path to PostgreSQL later
- PWA-friendly static structure with a manifest and service worker placeholder
- Dockerfile and `docker-compose.yml`
- pandas and openpyxl dependencies for later Excel export work

## Project structure

```text
farmsource/
  app/
    main.py
    config.py
    database.py
    models.py
    schemas.py
    routes/
    services/
    templates/
    static/
  admin/
  customer/
  driver/
  data/
    imports/
    exports/
  tests/
  requirements.txt
  Dockerfile
  docker-compose.yml
  .env.example
  README.md
  .gitignore
```

## Local setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Start the development server:

```bash
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/admin`
- `http://127.0.0.1:8000/customer`
- `http://127.0.0.1:8000/driver`
- `http://127.0.0.1:8000/health`

## Database initialization

The app creates the initial SQLAlchemy tables on startup. The default local database is:

```env
DATABASE_URL=sqlite:///./data/farmsource.db
```

To initialize manually, run:

```bash
python -c "from app.database import init_db; init_db()"
```

For PostgreSQL later, install an appropriate driver such as `psycopg` and set:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/farmsource
```

Alembic migrations can be added when the data model stabilizes beyond the v1 foundation.

## Docker

Copy the environment file:

```bash
cp .env.example .env
```

Build and run:

```bash
docker compose up --build
```

The app will be available at `http://127.0.0.1:8000`.

## Production startup

Recommended production command:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

For higher traffic, add workers based on server size:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000
```

## Linux deployment notes

1. Install Python 3.11+ and Git on the server.
2. Clone the repository.
3. Create `.env` from `.env.example`.
4. Set `DATABASE_URL` for SQLite or PostgreSQL.
5. Install dependencies in a virtual environment.
6. Run `python -c "from app.database import init_db; init_db()"`.
7. Start with gunicorn directly, Docker Compose, or a systemd service.
8. Put Nginx or another reverse proxy in front of port `8000`.
9. Monitor `/health` from your uptime or load balancer checks.

For SQLite on Linux, make sure the deployment user can write to the `data/` directory. For PostgreSQL, keep credentials in `.env` and never commit them.

## Tests

```bash
pytest
```
