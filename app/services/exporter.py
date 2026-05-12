from io import BytesIO

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Customer, DeliveryWindow, Driver, Order, Producer, Product, ProductAvailability, Route, RouteStop


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


def rows_to_excel(rows: list[dict], sheet_name: str) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output


def orders_to_excel(db: Session, query: Select[tuple[Order]] | None = None) -> BytesIO:
    if query is None:
        query = select(Order).order_by(Order.created_at.desc())
    orders = db.scalars(query).all()
    return rows_to_excel(
        [
            {
                "order_number": order.order_number,
                "status": order.order_status,
                "payment_status": order.payment_status,
                "customer": f"{order.customer.first_name} {order.customer.last_name}" if order.customer else "",
                "email": order.customer.email if order.customer else "",
                "delivery_window": order.delivery_window.name if order.delivery_window else "",
                "delivery_address": order.delivery_address,
                "city": order.delivery_city,
                "zip": order.delivery_zip,
                "total": order.total,
                "route_id": order.route_id,
                "created_at": order.created_at,
            }
            for order in orders
        ],
        "orders",
    )


def routes_to_excel(db: Session) -> BytesIO:
    routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
    rows = []
    for route in routes:
        rows.append(
            {
                "route_name": route.route_name,
                "status": route.route_status,
                "driver": f"{route.driver.first_name} {route.driver.last_name}" if route.driver else "",
                "region": route.region,
                "delivery_window": route.delivery_window.name if route.delivery_window else "",
                "stop_count": len(route.stops),
                "route_pay": route.route_pay,
                "route_bonus": route.route_bonus,
            }
        )
        for stop in route.stops:
            rows.append(
                {
                    "route_name": route.route_name,
                    "status": f"stop:{stop.stop_status}",
                    "driver": "",
                    "region": "",
                    "delivery_window": "",
                    "stop_count": stop.stop_sequence,
                    "route_pay": stop.order.order_number if stop.order else "",
                    "route_bonus": stop.order.delivery_address if stop.order else "",
                }
            )
    return rows_to_excel(rows, "routes")


def customers_to_excel(db: Session) -> BytesIO:
    customers = db.scalars(select(Customer).order_by(Customer.last_name, Customer.first_name)).all()
    return rows_to_excel(
        [
            {
                "name": f"{customer.first_name} {customer.last_name}",
                "email": customer.email,
                "phone": customer.phone,
                "address": customer.address_line_1,
                "city": customer.city,
                "state": customer.state,
                "zip": customer.zip_code,
                "active": customer.active,
            }
            for customer in customers
        ],
        "customers",
    )


def drivers_to_excel(db: Session) -> BytesIO:
    drivers = db.scalars(select(Driver).order_by(Driver.last_name, Driver.first_name)).all()
    return rows_to_excel(
        [
            {
                "name": f"{driver.first_name} {driver.last_name}",
                "email": driver.email,
                "phone": driver.phone,
                "territory": driver.territory,
                "vehicle_type": driver.vehicle_type,
                "active": driver.active,
            }
            for driver in drivers
        ],
        "drivers",
    )


def delivery_windows_to_excel(db: Session) -> BytesIO:
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    return rows_to_excel(
        [
            {
                "name": window.name,
                "delivery_date": window.delivery_date,
                "start_time": window.start_time,
                "end_time": window.end_time,
                "region": window.region,
                "max_orders": window.max_orders,
                "current_order_count": window.current_order_count,
                "active": window.active,
            }
            for window in windows
        ],
        "delivery_windows",
    )
