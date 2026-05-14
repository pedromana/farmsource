from io import BytesIO

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Customer, DeliveryWindow, Driver, DriverInterest, DriverPayout, MarketingContent, Order, Producer, ProducerInterest, Product, ProductAvailability, Route, RouteStop, WaitlistSignup
from app.services.delivery import order_summary, route_progress


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
                "progress_percent": route_progress(route)["percent"],
                "route_pay": route.route_pay,
                "route_bonus": route.route_bonus,
                "route_notes": route.route_notes or route.notes,
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
                    "progress_percent": "",
                    "route_pay": stop.order.order_number if stop.order else "",
                    "route_bonus": stop.address or (stop.order.delivery_address if stop.order else ""),
                    "route_notes": stop.delivery_notes,
                }
            )
    return rows_to_excel(rows, "routes")


def route_manifest_to_excel(db: Session, route_id: int | None = None) -> BytesIO:
    query = select(Route).order_by(Route.created_at.desc())
    if route_id:
        query = query.where(Route.id == route_id)
    routes = db.scalars(query).all()
    rows = []
    for route in routes:
        for stop in route.stops:
            rows.append(
                {
                    "route": route.route_name,
                    "delivery_window": route.delivery_window.name if route.delivery_window else "",
                    "driver": f"{route.driver.first_name} {route.driver.last_name}" if route.driver else "",
                    "stop_sequence": stop.stop_sequence,
                    "status": stop.stop_status,
                    "customer": stop.customer_name or "",
                    "address": stop.address or "",
                    "city": stop.city or "",
                    "state": stop.state or "",
                    "zip": stop.zip_code or "",
                    "order": stop.order.order_number if stop.order else "",
                    "order_summary": order_summary(stop.order),
                    "delivery_notes": stop.delivery_notes,
                    "driver_notes": stop.driver_notes,
                    "failed_reason": stop.failed_reason,
                }
            )
    return rows_to_excel(rows, "route_manifest")


def delivery_summary_to_excel(db: Session, status: str | None = None) -> BytesIO:
    query = select(RouteStop).order_by(RouteStop.stop_status, RouteStop.stop_sequence)
    if status:
        query = query.where(RouteStop.stop_status == status)
    stops = db.scalars(query).all()
    return rows_to_excel(
        [
            {
                "route": stop.route.route_name if stop.route else "",
                "driver": f"{stop.route.driver.first_name} {stop.route.driver.last_name}" if stop.route and stop.route.driver else "",
                "stop_sequence": stop.stop_sequence,
                "status": stop.stop_status,
                "customer": stop.customer_name,
                "address": stop.address,
                "order": stop.order.order_number if stop.order else "",
                "delivered_at": stop.delivered_at,
                "failed_reason": stop.failed_reason,
                "driver_notes": stop.driver_notes,
            }
            for stop in stops
        ],
        "delivery_summary",
    )


def completed_routes_to_excel(db: Session) -> BytesIO:
    routes = db.scalars(select(Route).where(Route.route_status == "completed").order_by(Route.updated_at.desc())).all()
    return rows_to_excel(
        [
            {
                "route": route.route_name,
                "driver": f"{route.driver.first_name} {route.driver.last_name}" if route.driver else "",
                "delivery_window": route.delivery_window.name if route.delivery_window else "",
                "stops": len(route.stops),
                "progress_percent": route_progress(route)["percent"],
                "route_pay": route.route_pay,
                "route_bonus": route.route_bonus,
            }
            for route in routes
        ],
        "completed_routes",
    )


def driver_payouts_to_excel(db: Session) -> BytesIO:
    payouts = db.scalars(select(DriverPayout).order_by(DriverPayout.created_at.desc())).all()
    return rows_to_excel(
        [
            {
                "driver": f"{payout.driver.first_name} {payout.driver.last_name}" if payout.driver else "",
                "route": payout.route.route_name if payout.route else "",
                "base_route_pay": payout.base_route_pay,
                "bonus_pay": payout.bonus_pay,
                "tip_amount": payout.tip_amount,
                "total_pay": payout.total_pay,
                "payout_status": payout.payout_status,
                "payout_notes": payout.payout_notes,
            }
            for payout in payouts
        ],
        "driver_payouts",
    )


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


def waitlist_to_excel(db: Session) -> BytesIO:
    rows = db.scalars(select(WaitlistSignup).order_by(WaitlistSignup.created_at.desc())).all()
    return rows_to_excel(
        [
            {
                "signup_type": row.signup_type,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "email": row.email,
                "phone": row.phone,
                "city": row.city,
                "state": row.state,
                "zip_code": row.zip_code,
                "source_page": row.source_page,
                "notes": row.notes,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "waitlist",
    )


def producer_interests_to_excel(db: Session) -> BytesIO:
    rows = db.scalars(select(ProducerInterest).order_by(ProducerInterest.created_at.desc())).all()
    return rows_to_excel(
        [
            {
                "business_name": row.business_name,
                "contact_name": row.contact_name,
                "email": row.email,
                "phone": row.phone,
                "website_url": row.website_url,
                "city": row.city,
                "state": row.state,
                "products": row.products,
                "delivery_capability": row.delivery_capability,
                "online_ordering": row.online_ordering,
                "notes": row.notes,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "producer_interests",
    )


def driver_interests_to_excel(db: Session) -> BytesIO:
    rows = db.scalars(select(DriverInterest).order_by(DriverInterest.created_at.desc())).all()
    return rows_to_excel(
        [
            {
                "first_name": row.first_name,
                "last_name": row.last_name,
                "email": row.email,
                "phone": row.phone,
                "city": row.city,
                "state": row.state,
                "vehicle_type": row.vehicle_type,
                "availability_notes": row.availability_notes,
                "territory_preference": row.territory_preference,
                "notes": row.notes,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "driver_interests",
    )


def marketing_content_to_excel(db: Session) -> BytesIO:
    rows = db.scalars(select(MarketingContent).order_by(MarketingContent.created_at.desc())).all()
    return rows_to_excel(
        [
            {
                "title": row.title,
                "content_type": row.content_type,
                "content_theme": row.content_theme,
                "target_platform": row.target_platform,
                "target_audience": row.target_audience,
                "status": row.status,
                "approved": row.approved,
                "scheduled_date": row.scheduled_date,
                "generated_caption": row.generated_caption,
                "generated_hashtags": row.generated_hashtags,
                "generated_video_prompt": row.generated_video_prompt,
                "generated_script": row.generated_script,
                "notes": row.notes,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "marketing_content",
    )
