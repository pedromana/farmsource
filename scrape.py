from __future__ import annotations

import argparse
import logging

from app.database import SessionLocal, init_db
from scrapers.runner import run_scrapers


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FarmSource provider scrapers.")
    parser.add_argument("--provider", help="Optional provider name to run.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    with SessionLocal() as session:
        runs = run_scrapers(session, args.provider)
        for run in runs:
            print(f"{run.provider_name}: {run.status} - {run.message}")


if __name__ == "__main__":
    main()
