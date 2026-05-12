from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CartSession, Customer, DeliveryWindow, Order, OrderItem
from app.services.cart import calculate_cart_totals
from app.services.catalog import current_availability_for_product, remaining_inventory


ORDER_STATUSES = {
    "pending",
    "confirmed",
    "packed",
    "assigned_to_route",
    "out_for_delivery",
    "delivered",
    "cancelled",
}

PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed", "refunded"}


def available_delivery_windows(db: Session) -> list[DeliveryWindow]:
    return db.scalars(
        select(DeliveryWindow)
        .where(
            DeliveryWindow.active.is_(True),
            DeliveryWindow.current_order_count < DeliveryWindow.max_orders,
        )
        .order_by(DeliveryWindow.delivery_date.asc(), DeliveryWindow.start_time.asc())
    ).all()


def create_pending_order(
    db: Session,
    cart: CartSession,
    delivery_window_id: int,
    customer_data: dict,
    customer_notes: str | None = None,
) -> Order:
    if not cart.items:
        raise ValueError("Cart is empty")

    delivery_window = db.get(DeliveryWindow, delivery_window_id)
    if not delivery_window or not delivery_window.active:
        raise ValueError("Delivery window is not available")
    if delivery_window.current_order_count >= delivery_window.max_orders:
        raise ValueError("Delivery window is full")

    for item in cart.items:
        availability = current_availability_for_product(item.product, delivery_window)
        if remaining_inventory(availability) < item.quantity:
            raise ValueError(f"{item.product.name} is no longer available in that quantity")

    customer = _get_or_create_customer(db, customer_data)
    totals = calculate_cart_totals(cart)
    order = Order(
        customer_id=customer.id,
        order_number=f"FS-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        order_status="pending",
        delivery_window_id=delivery_window.id,
        delivery_address=customer.address_line_1,
        delivery_city=customer.city,
        delivery_state=customer.state,
        delivery_zip=customer.zip_code,
        subtotal=totals.subtotal,
        delivery_fee=totals.delivery_fee,
        taxes=totals.taxes,
        total=totals.total,
        payment_status="pending",
        customer_notes=customer_notes,
    )
    db.add(order)
    db.flush()

    for item in cart.items:
        availability = current_availability_for_product(item.product, delivery_window)
        availability.reserved_quantity += item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.product.price,
                total_price=round(item.product.price * item.quantity, 2),
            )
        )

    delivery_window.current_order_count += 1
    cart.status = "converted"
    db.commit()
    db.refresh(order)
    return order


def mark_order_paid(db: Session, order: Order, payment_intent_id: str | None = None) -> None:
    order.payment_status = "paid"
    order.order_status = "confirmed"
    order.stripe_payment_intent_id = payment_intent_id or order.stripe_payment_intent_id
    order.paid_at = datetime.now(UTC)
    db.commit()


def cancel_unpaid_order(db: Session, order: Order) -> None:
    if order.payment_status == "paid":
        return
    order.payment_status = "failed"
    order.order_status = "cancelled"
    if order.delivery_window:
        order.delivery_window.current_order_count = max(order.delivery_window.current_order_count - 1, 0)
    for item in order.items:
        availability = current_availability_for_product(item.product, order.delivery_window)
        if availability:
            availability.reserved_quantity = max(availability.reserved_quantity - item.quantity, 0)
    db.commit()


def _get_or_create_customer(db: Session, data: dict) -> Customer:
    email = data["email"].strip().lower()
    customer = db.scalars(select(Customer).where(Customer.email == email)).first()
    if not customer:
        customer = Customer(email=email, **{key: value for key, value in data.items() if key != "email"})
        db.add(customer)
        db.flush()
    else:
        for key, value in data.items():
            setattr(customer, key, value)
    return customer
