# Codex Instructions For Farmsource

This repository has a remote development and production split. Follow these rules unless the user explicitly says otherwise.

## Environment Boundaries

- Use `~/src/farmsource` on `farmsource-dev` for development work.
- Treat `/opt/farmsource` on the server as production and do not modify it by default.
- Keep local Windows development available, but remote Linux dev is the recommended workflow.
- Never commit `.env` files, database files, backups, `node_modules`, `.venv`, or generated secrets.

## Remote Dev

SSH target:

```text
farmsource-dev
```

Remote dev path:

```bash
cd ~/src/farmsource
```

Run the app:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Run tests:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web pytest
```

Run migrations:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic upgrade head
```

## Production Safety

- Do not run `git reset`, `docker compose down -v`, migrations, restores, or destructive commands in `/opt/farmsource` unless the user explicitly asks for production work.
- Before any production change, create a database backup.
- Production should use `PRODUCTION_OPERATIONS.md` as the checklist.

## Validation Expectations

For backend/app changes, run:

```bash
pytest
```

For remote dev validation, run:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web pytest
```

For schema changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
pytest
```

## Useful Context Files

- `SESSION_HANDOFF.md`
- `REMOTE_DEV_SETUP.md`
- `PRODUCTION_OPERATIONS.md`
- `PROJECT_CONTEXT.md`
- `README.md`
