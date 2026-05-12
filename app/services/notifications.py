import logging

from app.models import Order


logger = logging.getLogger(__name__)


def send_order_confirmation_email(order: Order) -> None:
    logger.info("Email placeholder: order confirmation for %s", order.order_number)


def send_payment_success_email(order: Order) -> None:
    logger.info("Email placeholder: payment success for %s", order.order_number)


def send_delivery_confirmation_email(order: Order) -> None:
    logger.info("Email placeholder: delivery confirmation for %s", order.order_number)
