from io import BytesIO

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Producer


EXPORT_COLUMNS = [
    "id",
    "producer_name",
    "business_name",
    "website_url",
    "online_order_url",
    "source_listing_url",
    "city",
    "county",
    "state",
    "zip_code",
    "products",
    "producer_type",
    "delivery_available",
    "pickup_available",
    "online_ordering_confirmed",
    "qualified",
    "destination_type",
    "platform_detected",
    "confidence_score",
    "classification_reason",
    "contact_email",
    "contact_phone",
    "notes",
]


def producers_to_excel(db: Session, query: Select[tuple[Producer]] | None = None) -> BytesIO:
    if query is None:
        query = select(Producer).order_by(Producer.producer_name)
    producers = db.scalars(query).all()
    rows = [{column: getattr(producer, column) for column in EXPORT_COLUMNS} for producer in producers]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=EXPORT_COLUMNS).to_excel(writer, index=False, sheet_name="producers")
    output.seek(0)
    return output
