# Production Operations

This file covers the first production-readiness steps that should happen before Farmsource takes real customer orders.

## Migrations

Farmsource now includes Alembic. The initial migration captures the current SQLAlchemy schema.

For a new database:

```bash
alembic upgrade head
python seed_demo.py
```

For the remote Docker workflow:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web python seed_demo.py
```

For an existing database that was already created by `init_db()` before Alembic was added, do not run `upgrade head` blindly. First confirm the schema matches the initial migration, then stamp it:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml exec web alembic stamp head
```

Going forward, schema changes should be made through migrations:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

`init_db()` still exists for local v1 compatibility, but production should use Alembic as the source of truth.

## Backups

The Docker Postgres workflow includes helper scripts for compressed custom-format backups.

Create a backup:

```bash
scripts/backup_postgres.sh
```

Set a custom backup directory:

```bash
BACKUP_DIR=/opt/farmsource-backups scripts/backup_postgres.sh
```

Restore a backup into the currently configured Postgres database:

```bash
scripts/restore_postgres.sh backups/farmsource-YYYYMMDDTHHMMSSZ.dump
```

Restores are destructive because they use `pg_restore --clean --if-exists`. Test restores against dev before using them on production.

## Production Cutover Checklist

- Keep `/opt/farmsource` as the production checkout.
- Keep `~/src/farmsource` as the remote development checkout.
- Use separate `.env` files and separate Compose project names for production and development.
- Run `alembic upgrade head` during deploys after backing up the database.
- Store production backups outside the repo, preferably copied off-server.
- Rotate the server password and switch SSH to key-based auth.
- Put production behind HTTPS with `SESSION_COOKIE_SECURE=true`.
- Add Stripe webhook signature verification before live payments.
