import logging

import stripe
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order


logger = logging.getLogger(__name__)


def create_checkout_session(db: Session, order: Order) -> str:
    settings = get_settings()
    base_url = settings.app_base_url.rstrip("/")

    if not settings.stripe_secret_key:
        logger.info("Stripe key not configured; using local payment success redirect for order %s", order.order_number)
        return f"{base_url}/customer/payment-success?order_id={order.id}&local_payment=true"

    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=order.customer.email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.product.name},
                    "unit_amount": int(round(item.unit_price * 100)),
                },
                "quantity": item.quantity,
            }
            for item in order.items
        ]
        + (
            [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Scheduled delivery"},
                        "unit_amount": int(round(order.delivery_fee * 100)),
                    },
                    "quantity": 1,
                }
            ]
            if order.delivery_fee
            else []
        ),
        success_url=f"{base_url}/customer/payment-success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order.id}",
        cancel_url=f"{base_url}/customer/payment-cancelled?order_id={order.id}",
        metadata={"order_id": str(order.id), "order_number": order.order_number},
    )
    order.stripe_checkout_session_id = session.id
    db.commit()
    logger.info("Created Stripe Checkout Session %s for order %s", session.id, order.order_number)
    return session.url


def retrieve_payment_intent(session_id: str) -> str | None:
    settings = get_settings()
    if not settings.stripe_secret_key:
        return None
    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.retrieve(session_id)
    return session.payment_intent
