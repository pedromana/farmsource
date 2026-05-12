from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import BASE_DIR
from app.database import get_db
from app.models import Customer, Order, OrderItem, Product, ProductCategory
from app.services.cart import (
    add_to_cart,
    calculate_cart_totals,
    cart_item_count,
    get_or_create_cart,
    remove_cart_item,
    update_cart_item,
)
from app.services.catalog import (
    active_delivery_window,
    active_product_query,
    current_availability_for_product,
    featured_products,
    remaining_inventory,
)
from app.services.notifications import send_order_confirmation_email, send_payment_success_email
from app.services.orders import available_delivery_windows, cancel_unpaid_order, create_pending_order, mark_order_paid
from app.services.payments import create_checkout_session, retrieve_payment_intent


router = APIRouter(prefix="/customer", tags=["customer"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/catalog", response_class=HTMLResponse)
def catalog(request: Request, db: Annotated[Session, Depends(get_db)], q: str | None = None):
    window = active_delivery_window(db)
    window_id = window.id if window else None
    query = active_product_query(window_id)
    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    products = db.scalars(query.order_by(Product.featured.desc(), Product.name)).all()
    categories = db.scalars(
        select(ProductCategory).where(ProductCategory.active.is_(True)).order_by(ProductCategory.name)
    ).all()
    return templates.TemplateResponse(
        "customer_catalog.html",
        {
            "request": request,
            "products": products,
            "featured_products": featured_products(db),
            "categories": categories,
            "delivery_window": window,
            "remaining_inventory": remaining_inventory,
            "current_availability_for_product": current_availability_for_product,
            "placeholder_image": _placeholder_image(),
            "cart_count": _cart_count(request, db),
            "q": q or "",
        },
    )


@router.get("/category/{category_id}", response_class=HTMLResponse)
def category_catalog(category_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    category = db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    window = active_delivery_window(db)
    window_id = window.id if window else None
    products = db.scalars(
        active_product_query(window_id)
        .where(Product.category_id == category_id)
        .order_by(Product.name)
    ).all()
    categories = db.scalars(
        select(ProductCategory).where(ProductCategory.active.is_(True)).order_by(ProductCategory.name)
    ).all()
    return templates.TemplateResponse(
        "customer_category.html",
        {
            "request": request,
            "category": category,
            "products": products,
            "categories": categories,
            "delivery_window": window,
            "remaining_inventory": remaining_inventory,
            "current_availability_for_product": current_availability_for_product,
            "placeholder_image": _placeholder_image(),
            "cart_count": _cart_count(request, db),
        },
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    product = db.scalars(
        select(Product)
        .options(
            selectinload(Product.producer),
            selectinload(Product.category),
            selectinload(Product.availability),
            selectinload(Product.images),
        )
        .where(Product.id == product_id)
    ).first()
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Product not found")
    window = active_delivery_window(db)
    availability = current_availability_for_product(product, window)
    return templates.TemplateResponse(
        "customer_product.html",
        {
            "request": request,
            "product": product,
            "delivery_window": window,
            "availability": availability,
            "remaining_inventory": remaining_inventory,
            "placeholder_image": _placeholder_image(),
            "cart_count": _cart_count(request, db),
        },
    )


@router.post("/cart/add")
def add_cart_item(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    product_id: Annotated[int, Form()],
    quantity: Annotated[int, Form()] = 1,
):
    cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
    try:
        add_to_cart(db, cart, product_id, quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.expire(cart, ["items"])
    if _wants_json(request):
        response = JSONResponse(_cart_payload(cart))
    else:
        response = RedirectResponse(request.headers.get("referer") or "/customer/catalog", status_code=303)
    response.set_cookie("farmsource_cart", cart.session_id, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.get("/cart/summary")
def cart_summary(request: Request, db: Annotated[Session, Depends(get_db)]):
    cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
    response = JSONResponse(_cart_payload(cart))
    response.set_cookie("farmsource_cart", cart.session_id, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
    response = templates.TemplateResponse(
        "customer_cart.html",
        {"request": request, "cart": cart, "totals": calculate_cart_totals(cart), "cart_count": cart_item_count(cart)},
    )
    response.set_cookie("farmsource_cart", cart.session_id, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.post("/cart/update")
def update_cart(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    item_id: Annotated[int, Form()],
    quantity: Annotated[int, Form()],
):
    update_cart_item(db, item_id, quantity)
    if _wants_json(request):
        cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
        return JSONResponse(_cart_payload(cart))
    return RedirectResponse("/customer/cart", status_code=303)


@router.post("/cart/remove")
def remove_from_cart(db: Annotated[Session, Depends(get_db)], item_id: Annotated[int, Form()]):
    remove_cart_item(db, item_id)
    return RedirectResponse("/customer/cart", status_code=303)


@router.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
    windows = available_delivery_windows(db)
    response = templates.TemplateResponse(
        "customer_checkout.html",
        {
            "request": request,
            "cart": cart,
            "totals": calculate_cart_totals(cart),
            "windows": windows,
            "cart_count": cart_item_count(cart),
        },
    )
    response.set_cookie("farmsource_cart", cart.session_id, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@router.post("/checkout")
async def start_checkout(request: Request, db: Annotated[Session, Depends(get_db)]):
    cart = get_or_create_cart(db, request.cookies.get("farmsource_cart"))
    form = await request.form()
    customer_data = {
        "first_name": _required(form.get("first_name"), "First name"),
        "last_name": _required(form.get("last_name"), "Last name"),
        "email": _required(form.get("email"), "Email"),
        "phone": _optional(form.get("phone")),
        "address_line_1": _required(form.get("address_line_1"), "Address"),
        "address_line_2": _optional(form.get("address_line_2")),
        "city": _required(form.get("city"), "City"),
        "state": _required(form.get("state"), "State"),
        "zip_code": _required(form.get("zip_code"), "ZIP code"),
        "delivery_notes": _optional(form.get("delivery_notes")),
    }
    try:
        order = create_pending_order(
            db,
            cart,
            int(_required(form.get("delivery_window_id"), "Delivery window")),
            customer_data,
            _optional(form.get("customer_notes")),
        )
        checkout_url = create_checkout_session(db, order)
        send_order_confirmation_email(order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = RedirectResponse(checkout_url, status_code=303)
    response.delete_cookie("farmsource_cart")
    return response


@router.get("/payment-success")
def payment_success(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    order_id: int,
    session_id: str | None = None,
    local_payment: bool = False,
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payment_intent_id = retrieve_payment_intent(session_id) if session_id else None
    mark_order_paid(db, order, payment_intent_id)
    send_payment_success_email(order)
    return RedirectResponse(f"/customer/order-confirmation/{order.id}", status_code=303)


@router.get("/payment-cancelled", response_class=HTMLResponse)
def payment_cancelled(request: Request, db: Annotated[Session, Depends(get_db)], order_id: int | None = None):
    order = db.get(Order, order_id) if order_id else None
    if order:
        cancel_unpaid_order(db, order)
    return templates.TemplateResponse("customer_payment_cancelled.html", {"request": request, "order": order, "cart_count": 0})


@router.get("/order-confirmation/{order_id}", response_class=HTMLResponse)
def order_confirmation(order_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    order = _get_order(db, order_id)
    return templates.TemplateResponse("customer_order_confirmation.html", {"request": request, "order": order, "cart_count": 0})


@router.get("/orders", response_class=HTMLResponse)
def customer_orders(request: Request, db: Annotated[Session, Depends(get_db)], email: str | None = None):
    orders = []
    if email:
        orders = db.scalars(
            select(Order).join(Customer).where(Customer.email == email.strip().lower()).order_by(Order.created_at.desc())
        ).all()
    return templates.TemplateResponse(
        "customer_orders.html",
        {"request": request, "orders": orders, "email": email or "", "cart_count": _cart_count(request, db)},
    )


@router.get("/order/{order_id}", response_class=HTMLResponse)
def order_detail(order_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        "customer_order_detail.html",
        {"request": request, "order": _get_order(db, order_id), "cart_count": _cart_count(request, db)},
    )


@router.post("/stripe/webhook")
async def stripe_webhook_placeholder(request: Request):
    return {"status": "placeholder", "detail": "Stripe webhook verification will be added in a future phase."}


def _placeholder_image() -> str:
    return "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80"


def _cart_count(request: Request, db: Session) -> int:
    session_id = request.cookies.get("farmsource_cart")
    if not session_id:
        return 0
    cart = get_or_create_cart(db, session_id)
    return cart_item_count(cart)


def _get_order(db: Session, order_id: int) -> Order:
    order = db.scalars(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product), selectinload(Order.customer), selectinload(Order.delivery_window))
        .where(Order.id == order_id)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _optional(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _required(value, label: str) -> str:
    value = _optional(value)
    if not value:
        raise HTTPException(status_code=400, detail=f"{label} is required")
    return value


def _wants_json(request: Request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _cart_payload(cart) -> dict:
    totals = calculate_cart_totals(cart)
    return {
        "count": cart_item_count(cart),
        "subtotal": totals.subtotal,
        "delivery_fee": totals.delivery_fee,
        "taxes": totals.taxes,
        "total": totals.total,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.product.price,
                "total_price": round(item.quantity * item.product.price, 2),
            }
            for item in cart.items
        ],
    }
