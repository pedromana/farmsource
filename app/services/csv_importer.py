import csv
import json
from dataclasses import dataclass
from io import StringIO

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ImportErrorRow, ImportRun, Producer
from app.services.classification import classify_producer_destination


FIELD_ALIASES = {
    "producer_name": ("producer_name", "producer", "farm_name", "farm", "name", "vendor", "supplier", "source_name"),
    "business_name": ("business_name", "business", "company", "organization", "org_name"),
    "website_url": ("website_url", "website", "site", "url", "farm_url", "business_url", "producer_url"),
    "online_order_url": ("online_order_url", "order_url", "shop_url", "store_url", "online_store", "buy_url", "market_url"),
    "source_listing_url": ("source_listing_url", "listing_url", "directory_url", "profile_url", "source_url"),
    "city": ("city", "town"),
    "county": ("county",),
    "state": ("state", "province"),
    "zip_code": ("zip_code", "zip", "postal_code", "postcode"),
    "products": ("products", "product", "offerings", "categories", "produce", "items"),
    "producer_type": ("producer_type", "type", "category", "business_type"),
    "delivery_available": ("delivery_available", "delivery", "delivers", "home_delivery"),
    "pickup_available": ("pickup_available", "pickup", "farm_pickup", "local_pickup"),
    "contact_email": ("contact_email", "email", "e-mail"),
    "contact_phone": ("contact_phone", "phone", "telephone", "mobile"),
    "notes": ("notes", "description", "summary", "details"),
}

BOOLEAN_TRUE = {"true", "yes", "y", "1", "available", "x"}


@dataclass(frozen=True)
class ImportSummary:
    import_run_id: int
    total_rows: int
    imported_rows: int
    skipped_rows: int
    error_count: int


def import_producers_from_csv(
    db: Session,
    source_id: int | None,
    filename: str,
    content: bytes,
) -> ImportSummary:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    import_run = ImportRun(source_id=source_id, filename=filename)
    db.add(import_run)
    db.flush()

    if not reader.fieldnames:
        _record_error(db, import_run.id, 0, "CSV file does not contain a header row.", {})
        import_run.error_count = 1
        db.commit()
        return _summary(import_run)

    header_map = _build_header_map(reader.fieldnames)

    for row_number, row in enumerate(reader, start=2):
        import_run.total_rows += 1
        try:
            producer_data = _map_row(row, header_map)
            if not producer_data["producer_name"]:
                import_run.skipped_rows += 1
                import_run.error_count += 1
                _record_error(db, import_run.id, row_number, "Missing producer name.", row)
                continue

            producer_data["source_id"] = source_id
            if _is_duplicate(db, producer_data):
                import_run.skipped_rows += 1
                _record_error(db, import_run.id, row_number, "Skipped duplicate producer.", row)
                continue

            classification = classify_producer_destination(
                producer_data.get("website_url"),
                producer_data.get("online_order_url"),
            )
            producer = Producer(
                **producer_data,
                destination_type=classification.destination_type,
                platform_detected=classification.platform_detected,
                confidence_score=classification.confidence_score,
                online_ordering_confirmed=classification.online_ordering_confirmed,
                qualified=classification.qualified,
                classification_reason=classification.reason,
            )
            db.add(producer)
            import_run.imported_rows += 1
        except Exception as exc:
            import_run.skipped_rows += 1
            import_run.error_count += 1
            _record_error(db, import_run.id, row_number, str(exc), row)

    db.commit()
    return _summary(import_run)


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    normalized_headers = {_normalize_header(header): header for header in fieldnames}
    header_map = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                header_map[field] = normalized_headers[alias]
                break
    return header_map


def _map_row(row: dict[str, str], header_map: dict[str, str]) -> dict:
    data = {}
    for field in FIELD_ALIASES:
        source_header = header_map.get(field)
        value = row.get(source_header, "") if source_header else ""
        data[field] = _clean(value)

    data["producer_name"] = data["producer_name"] or data["business_name"]
    data["delivery_available"] = _to_bool(data["delivery_available"])
    data["pickup_available"] = _to_bool(data["pickup_available"])
    return data


def _is_duplicate(db: Session, data: dict) -> bool:
    checks = []
    for field in ("website_url", "online_order_url", "source_listing_url"):
        value = data.get(field)
        if value:
            checks.append(getattr(Producer, field) == value)

    producer_name = data.get("producer_name")
    city = data.get("city")
    if producer_name and city:
        checks.append(
            (Producer.producer_name == producer_name)
            & (Producer.city == city)
            & (Producer.state == data.get("state"))
        )

    if not checks:
        return False

    return db.scalar(select(Producer.id).where(or_(*checks)).limit(1)) is not None


def _record_error(db: Session, import_run_id: int, row_number: int, reason: str, row: dict) -> None:
    db.add(
        ImportErrorRow(
            import_run_id=import_run_id,
            row_number=row_number,
            reason=reason[:255],
            raw_data=json.dumps(row),
        )
    )


def _summary(import_run: ImportRun) -> ImportSummary:
    return ImportSummary(
        import_run_id=import_run.id,
        total_rows=import_run.total_rows,
        imported_rows=import_run.imported_rows,
        skipped_rows=import_run.skipped_rows,
        error_count=import_run.error_count,
    )


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _to_bool(value: str | None) -> bool:
    return bool(value and value.strip().lower() in BOOLEAN_TRUE)
