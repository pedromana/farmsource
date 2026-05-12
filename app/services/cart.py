from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CartItem, CartSession, Product
from app.services.catalog import active_delivery_window, current_availability_for_product, remaining_inventory


DELIVERY_FEE = 6.99
TAX_RATE = 0.0


@dataclass(frozen=True)
class CartTotals:
    subtotal: float
    delivery_fee: float
    taxes: float
    total: float


def get_or_create_cart(db: Session, session_id: str | None) -> CartSession:
    if session_id:
        cart = db.scalars(
            select(CartSession)
            .options(selectinload(CartSession.items).selectinload(CartItem.product))
            .where(CartSession.session_id == session_id, CartSession.status == "active")
        ).first()
        if cart:
            return cart

    cart = CartSession(session_id=uuid4().hex, status="active")
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def add_to_cart(db: Session, cart: CartSession, product_id: int, quantity: int = 1) -> None:
    quantity = max(quantity, 1)
    product = db.get(Product, product_id)
    if not product:
        raise ValueError("Product not found")
    window = active_delivery_window(db)
    availability = current_availability_for_product(product, window)
    remaining = remaining_inventory(availability)
    existing = next((item for item in cart.items if item.product_id == product_id), None)
    current_quantity = existing.quantity if existing else 0
    if remaining < current_quantity + quantity:
        raise ValueError("Not enough inventory available")
    if existing:
        existing.quantity += quantity
    else:
        db.add(CartItem(cart_session_id=cart.id, product_id=product_id, quantity=quantity))
    db.commit()


def update_cart_item(db: Session, item_id: int, quantity: int) -> None:
    item = db.get(CartItem, item_id)
    if not item:
        return
    if quantity <= 0:
        db.delete(item)
    else:
        item.quantity = quantity
    db.commit()


def remove_cart_item(db: Session, item_id: int) -> None:
    item = db.get(CartItem, item_id)
    if item:
        db.delete(item)
        db.commit()


def calculate_cart_totals(cart: CartSession) -> CartTotals:
    subtotal = round(sum(item.quantity * item.product.price for item in cart.items), 2)
    delivery_fee = DELIVERY_FEE if subtotal > 0 else 0.0
    taxes = round(subtotal * TAX_RATE, 2)
    return CartTotals(subtotal, delivery_fee, taxes, round(subtotal + delivery_fee + taxes, 2))


def cart_item_count(cart: CartSession) -> int:
    return sum(item.quantity for item in cart.items)
