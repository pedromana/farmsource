from io import BytesIO

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Producer
from app.models import Product, ProductAvailability


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


PRODUCT_EXPORT_COLUMNS = [
    "id",
    "name",
    "sku",
    "unit",
    "price",
    "compare_at_price",
    "featured",
    "active",
    "seasonal",
    "delivery_eligible",
    "producer_name",
    "category_name",
]


def products_to_excel(db: Session, query: Select[tuple[Product]] | None = None) -> BytesIO:
    if query is None:
        query = select(Product).order_by(Product.name)
    products = db.scalars(query).all()
    rows = [
        {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "price": product.price,
            "compare_at_price": product.compare_at_price,
            "featured": product.featured,
            "active": product.active,
            "seasonal": product.seasonal,
            "delivery_eligible": product.delivery_eligible,
            "producer_name": product.producer.producer_name if product.producer else "",
            "category_name": product.category.name if product.category else "",
        }
        for product in products
    ]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=PRODUCT_EXPORT_COLUMNS).to_excel(writer, index=False, sheet_name="products")
    output.seek(0)
    return output


def availability_to_excel(db: Session, query: Select[tuple[ProductAvailability]] | None = None) -> BytesIO:
    if query is None:
        query = select(ProductAvailability).order_by(ProductAvailability.id)
    availability_rows = db.scalars(query).all()
    rows = [
        {
            "product": row.product.name if row.product else "",
            "delivery_window": row.delivery_window.name if row.delivery_window else "",
            "available_quantity": row.available_quantity,
            "reserved_quantity": row.reserved_quantity,
            "remaining_quantity": max(row.available_quantity - row.reserved_quantity, 0),
            "status": row.status,
            "available_from": row.available_from,
            "available_until": row.available_until,
        }
        for row in availability_rows
    ]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="availability")
    output.seek(0)
    return output
