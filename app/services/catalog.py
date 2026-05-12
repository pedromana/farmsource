from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import DeliveryWindow, Product, ProductAvailability


LOW_INVENTORY_THRESHOLD = 5


def remaining_inventory(availability: ProductAvailability | None) -> int:
    if availability is None:
        return 0
    return max(availability.available_quantity - availability.reserved_quantity, 0)


def is_product_available(product: Product, delivery_window: DeliveryWindow | None = None) -> bool:
    if not product.active or not product.delivery_eligible:
        return False
    availability = current_availability_for_product(product, delivery_window)
    return bool(availability and availability.status == "active" and remaining_inventory(availability) > 0)


def current_availability_for_product(
    product: Product,
    delivery_window: DeliveryWindow | None = None,
) -> ProductAvailability | None:
    now = datetime.now(UTC)
    for availability in product.availability:
        if delivery_window and availability.delivery_window_id != delivery_window.id:
            continue
        if availability.status != "active":
            continue
        available_from = _normalize_datetime(availability.available_from)
        available_until = _normalize_datetime(availability.available_until)
        if available_from and available_from > now:
            continue
        if available_until and available_until < now:
            continue
        if remaining_inventory(availability) > 0:
            return availability
    return None


def active_delivery_window(db: Session) -> DeliveryWindow | None:
    return db.scalars(
        select(DeliveryWindow)
        .where(DeliveryWindow.active.is_(True))
        .order_by(DeliveryWindow.delivery_date.asc(), DeliveryWindow.id.asc())
        .limit(1)
    ).first()


def active_product_query(delivery_window_id: int | None = None) -> Select[tuple[Product]]:
    now = datetime.now(UTC)
    query = (
        select(Product)
        .join(ProductAvailability)
        .options(selectinload(Product.producer), selectinload(Product.category), selectinload(Product.availability))
        .where(
            Product.active.is_(True),
            Product.delivery_eligible.is_(True),
            ProductAvailability.status == "active",
            ProductAvailability.available_quantity > ProductAvailability.reserved_quantity,
            or_(ProductAvailability.available_from.is_(None), ProductAvailability.available_from <= now),
            or_(ProductAvailability.available_until.is_(None), ProductAvailability.available_until >= now),
        )
    )
    if delivery_window_id:
        query = query.where(ProductAvailability.delivery_window_id == delivery_window_id)
    return query.distinct()


def featured_products(db: Session, limit: int = 6) -> list[Product]:
    window = active_delivery_window(db)
    window_id = window.id if window else None
    return db.scalars(
        active_product_query(window_id)
        .where(Product.featured.is_(True))
        .order_by(Product.name)
        .limit(limit)
    ).all()


def low_inventory_availability(db: Session, threshold: int = LOW_INVENTORY_THRESHOLD) -> list[ProductAvailability]:
    return db.scalars(
        select(ProductAvailability)
        .options(selectinload(ProductAvailability.product), selectinload(ProductAvailability.delivery_window))
        .where(
            ProductAvailability.status == "active",
            ProductAvailability.available_quantity > ProductAvailability.reserved_quantity,
            (ProductAvailability.available_quantity - ProductAvailability.reserved_quantity) <= threshold,
        )
        .order_by(ProductAvailability.available_quantity - ProductAvailability.reserved_quantity)
    ).all()


def availability_window_bounds(days: int = 7) -> tuple[datetime, datetime]:
    start = datetime.now(UTC)
    return start, start + timedelta(days=days)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
