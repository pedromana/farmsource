import argparse

from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.services.seed import seed_sample_catalog


SAFE_RESET_ENVS = {"local", "development", "dev", "test"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Farmsource v1 demo data.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding. Only allowed in local/development/test environments.")
    args = parser.parse_args()

    settings = get_settings()
    if args.reset:
        if settings.app_env.lower() not in SAFE_RESET_ENVS:
            raise SystemExit(f"Refusing reset when APP_ENV={settings.app_env!r}. Allowed values: {', '.join(sorted(SAFE_RESET_ENVS))}.")
        if not settings.database_url.startswith("sqlite"):
            raise SystemExit("Refusing reset for non-SQLite databases. Reset production-like databases manually with backups.")
        Base.metadata.drop_all(bind=engine)

    init_db()
    with SessionLocal() as db:
        seed_sample_catalog(db)

    action = "Reset and seeded" if args.reset else "Seeded"
    print(f"{action} Farmsource demo data for APP_ENV={settings.app_env}.")
    print("Admin: admin@farmsource.local / ChangeMe123!")
    print("Driver: driver@example.com / Driver123!")


if __name__ == "__main__":
    main()
