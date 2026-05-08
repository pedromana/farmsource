from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Query, Session

from app.database import PROJECT_ROOT
from app.models import Producer

EXPORT_COLUMNS = [
    "farm_name",
    "city",
    "county",
    "state",
    "products",
    "source_name",
    "source_listing_url",
    "buy_online_url",
    "website_url",
    "destination_type",
    "platform_detected",
    "confidence_score",
    "classification_reason",
    "pickup_available",
    "delivery_available",
    "phone",
    "email_or_contact_url",
    "last_checked_date",
]


def producer_query(session: Session, filters: dict[str, Any], qualified_only: bool = True) -> Query:
    query = session.query(Producer)
    if qualified_only:
        query = query.filter(Producer.online_ordering_confirmed.is_(True))
    if search := filters.get("search"):
        query = query.filter(Producer.farm_name.ilike(f"%{search}%"))
    for key, column in {
        "city": Producer.city,
        "county": Producer.county,
        "state": Producer.state,
        "source": Producer.source_name,
        "platform": Producer.platform_detected,
        "destination_type": Producer.destination_type,
    }.items():
        if value := filters.get(key):
            query = query.filter(column.ilike(f"%{value}%"))
    if products := filters.get("products"):
        query = query.filter(Producer.products.ilike(f"%{products}%"))
    if filters.get("delivery") in {"true", True}:
        query = query.filter(Producer.delivery_available.is_(True))
    if filters.get("pickup") in {"true", True}:
        query = query.filter(Producer.pickup_available.is_(True))
    return query


def export_producers(session: Session, filters: dict[str, Any] | None = None) -> Path:
    filters = filters or {}
    rows = producer_query(session, filters, qualified_only=True).order_by(Producer.confidence_score.desc()).all()
    data = [{column: getattr(row, column) for column in EXPORT_COLUMNS} for row in rows]
    frame = pd.DataFrame(data, columns=EXPORT_COLUMNS)
    export_dir = PROJECT_ROOT / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"qualified_producers_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    frame.to_excel(path, index=False)
    return path
