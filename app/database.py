from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401

    _migrate_legacy_sqlite_schema()
    Base.metadata.create_all(bind=engine)


def check_database() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def _migrate_legacy_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    producer_columns = set()
    if "producers" in table_names:
        producer_columns = {column["name"] for column in inspector.get_columns("producers")}
    product_columns = set()
    if "products" in table_names:
        product_columns = {column["name"] for column in inspector.get_columns("products")}

    with engine.begin() as connection:
        if "producers" in table_names and "producer_name" not in producer_columns:
            connection.execute(text("DROP TABLE IF EXISTS producers"))
        if "products" in table_names and "producer_id" not in product_columns:
            connection.execute(text("DROP TABLE IF EXISTS products"))
        if "delivery_windows" in table_names:
            window_columns = {column["name"] for column in inspector.get_columns("delivery_windows")}
            delivery_window_additions = {
                "start_time": "VARCHAR(20)",
                "end_time": "VARCHAR(20)",
                "max_orders": "INTEGER NOT NULL DEFAULT 40",
                "current_order_count": "INTEGER NOT NULL DEFAULT 0",
            }
            for column_name, ddl in delivery_window_additions.items():
                if column_name not in window_columns:
                    connection.execute(text(f"ALTER TABLE delivery_windows ADD COLUMN {column_name} {ddl}"))
        if "routes" in table_names:
            route_columns = {column["name"] for column in inspector.get_columns("routes")}
            route_additions = {
                "estimated_stop_count": "INTEGER NOT NULL DEFAULT 0",
                "estimated_order_count": "INTEGER NOT NULL DEFAULT 0",
                "reassignment_priority": "BOOLEAN NOT NULL DEFAULT 0",
                "assignment_notes": "TEXT",
                "route_notes": "TEXT",
            }
            for column_name, ddl in route_additions.items():
                if column_name not in route_columns:
                    connection.execute(text(f"ALTER TABLE routes ADD COLUMN {column_name} {ddl}"))
        if "route_stops" in table_names:
            stop_columns = {column["name"] for column in inspector.get_columns("route_stops")}
            stop_additions = {
                "customer_name": "VARCHAR(255)",
                "address": "VARCHAR(255)",
                "city": "VARCHAR(120)",
                "state": "VARCHAR(40)",
                "zip_code": "VARCHAR(20)",
                "driver_notes": "TEXT",
                "failed_reason": "TEXT",
                "proof_of_delivery_url": "VARCHAR(1000)",
            }
            for column_name, ddl in stop_additions.items():
                if column_name not in stop_columns:
                    connection.execute(text(f"ALTER TABLE route_stops ADD COLUMN {column_name} {ddl}"))
        if "drivers" in table_names:
            driver_columns = {column["name"] for column in inspector.get_columns("drivers")}
            if "password_hash" not in driver_columns:
                connection.execute(text("ALTER TABLE drivers ADD COLUMN password_hash VARCHAR(255)"))
