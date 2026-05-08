from __future__ import annotations

import argparse

from app.database import SessionLocal, init_db
from app.exporter import export_producers


def main() -> None:
    parser = argparse.ArgumentParser(description="Export qualified FarmSource producers to Excel.")
    parser.add_argument("--search")
    parser.add_argument("--city")
    parser.add_argument("--county")
    parser.add_argument("--state")
    parser.add_argument("--products")
    parser.add_argument("--platform")
    parser.add_argument("--source")
    args = parser.parse_args()
    init_db()
    filters = {key: value for key, value in vars(args).items() if value}
    with SessionLocal() as session:
        path = export_producers(session, filters)
    print(path)


if __name__ == "__main__":
    main()
