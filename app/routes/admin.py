from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import (
    Customer,
    DeliveryWindow,
    Driver,
    DriverPayout,
    ImportRun,
    Order,
    Producer,
    Product,
    ProductAvailability,
    ProductCategory,
    ProductImage,
    Route,
    RouteStop,
    Source,
)
from app.services.auth import hash_password, require_admin
from app.services.catalog import LOW_INVENTORY_THRESHOLD, low_inventory_availability
from app.services.classification import classify_producer_destination
from app.services.csv_importer import import_producers_from_csv
from app.services.delivery import assign_route_to_driver, ensure_route_payout, order_summary, refresh_route_estimates, route_driver_suggestions, route_progress, sync_stop_from_order
from app.services.exporter import availability_to_excel, completed_routes_to_excel, customers_to_excel, delivery_summary_to_excel, delivery_windows_to_excel, driver_payouts_to_excel, drivers_to_excel, orders_to_excel, producers_to_excel, products_to_excel, route_manifest_to_excel, routes_to_excel


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("")
def admin_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    return RedirectResponse("/admin/dashboard", status_code=303)


@router.get("/dashboard")
def operations_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    order_status_rows = db.execute(select(Order.order_status, func.count(Order.id)).group_by(Order.order_status)).all()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "source_count": db.scalar(select(func.count(Source.id))),
            "producer_count": db.scalar(select(func.count(Producer.id))),
            "qualified_count": db.scalar(select(func.count(Producer.id)).where(Producer.qualified.is_(True))),
            "product_count": db.scalar(select(func.count(Product.id))),
            "active_product_count": db.scalar(select(func.count(Product.id)).where(Product.active.is_(True))),
            "upcoming_window_count": db.scalar(select(func.count(DeliveryWindow.id)).where(DeliveryWindow.active.is_(True))),
            "open_order_count": db.scalar(select(func.count(Order.id)).where(Order.order_status.in_(["pending", "confirmed", "packed", "assigned_to_route"]))),
            "active_route_count": db.scalar(select(func.count(Route.id)).where(Route.route_status.in_(["planned", "assigned", "in_progress"]))),
            "active_driver_count": db.scalar(select(func.count(Driver.id)).where(Driver.active.is_(True))),
            "total_sales": db.scalar(select(func.coalesce(func.sum(Order.total), 0.0)).where(Order.payment_status == "paid")),
            "low_inventory_count": len(low_inventory_availability(db)),
            "orders_by_status": order_status_rows,
        },
    )


@router.get("/orders")
def list_orders(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    delivery_window_id: int | None = None,
    route_id: int | None = None,
    customer: str | None = None,
):
    query = _filtered_order_query(status, delivery_window_id, route_id, customer)
    orders = db.scalars(query.order_by(Order.created_at.desc())).all()
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    routes = db.scalars(select(Route).order_by(Route.route_name)).all()
    return templates.TemplateResponse(
        "admin_orders.html",
        {"request": request, "orders": orders, "windows": windows, "routes": routes, "filters": {"status": status or "", "delivery_window_id": delivery_window_id, "route_id": route_id, "customer": customer or ""}},
    )


@router.get("/orders/{order_id}")
def order_detail(order_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    routes = db.scalars(select(Route).order_by(Route.route_name)).all()
    return templates.TemplateResponse("admin_order_detail.html", {"request": request, "order": order, "routes": routes})


@router.post("/orders/{order_id}")
async def update_order(order_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    form = await request.form()
    order.order_status = str(form.get("order_status") or order.order_status)
    order.route_id = _optional_int(form.get("route_id"))
    order.internal_notes = _optional(form.get("internal_notes"))
    if order.route_id and not db.scalars(select(RouteStop).where(RouteStop.route_id == order.route_id, RouteStop.order_id == order.id)).first():
        max_sequence = db.scalar(select(func.coalesce(func.max(RouteStop.stop_sequence), 0)).where(RouteStop.route_id == order.route_id))
        stop = RouteStop(route_id=order.route_id, order_id=order.id, stop_sequence=max_sequence + 1, delivery_notes=order.customer.delivery_notes if order.customer else None)
        db.add(stop)
        db.flush()
        sync_stop_from_order(stop)
        route = db.get(Route, order.route_id)
        if route:
            refresh_route_estimates(route)
            ensure_route_payout(db, route)
    db.commit()
    return RedirectResponse(f"/admin/orders/{order.id}", status_code=303)


@router.get("/customers")
def list_customers(request: Request, db: Annotated[Session, Depends(get_db)], q: str | None = None):
    query = select(Customer)
    if q:
        query = query.where((Customer.email.ilike(f"%{q}%")) | (Customer.last_name.ilike(f"%{q}%")))
    customers = db.scalars(query.order_by(Customer.last_name, Customer.first_name)).all()
    return templates.TemplateResponse("admin_customers.html", {"request": request, "customers": customers, "q": q or ""})


@router.get("/drivers")
def list_drivers(request: Request, db: Annotated[Session, Depends(get_db)]):
    drivers = db.scalars(select(Driver).order_by(Driver.last_name, Driver.first_name)).all()
    payouts = db.scalars(select(DriverPayout).order_by(DriverPayout.created_at.desc()).limit(25)).all()
    return templates.TemplateResponse("admin_drivers.html", {"request": request, "drivers": drivers, "driver": None, "payouts": payouts})


@router.get("/drivers/{driver_id}")
def edit_driver(driver_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = db.get(Driver, driver_id)
    drivers = db.scalars(select(Driver).order_by(Driver.last_name, Driver.first_name)).all()
    payouts = db.scalars(select(DriverPayout).where(DriverPayout.driver_id == driver_id).order_by(DriverPayout.created_at.desc())).all()
    return templates.TemplateResponse("admin_drivers.html", {"request": request, "drivers": drivers, "driver": driver, "payouts": payouts})


@router.post("/drivers")
@router.post("/drivers/{driver_id}")
async def save_driver(request: Request, db: Annotated[Session, Depends(get_db)], driver_id: int | None = None):
    form = await request.form()
    driver = db.get(Driver, driver_id) if driver_id else Driver()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    driver.first_name = _required_text(form.get("first_name"), "first_name")
    driver.last_name = _required_text(form.get("last_name"), "last_name")
    driver.email = _optional(form.get("email"))
    driver.phone = _optional(form.get("phone"))
    driver.territory = _optional(form.get("territory"))
    driver.vehicle_type = _optional(form.get("vehicle_type"))
    password = _optional(form.get("password"))
    if password:
        driver.password_hash = hash_password(password)
    driver.active = form.get("active") == "on"
    driver.notes = _optional(form.get("notes"))
    db.add(driver)
    db.commit()
    return RedirectResponse("/admin/drivers", status_code=303)


@router.get("/delivery-windows")
def list_delivery_windows(request: Request, db: Annotated[Session, Depends(get_db)]):
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    return templates.TemplateResponse("admin_delivery_windows.html", {"request": request, "windows": windows, "window": None})


@router.get("/delivery-windows/{window_id}")
def edit_delivery_window(window_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    window = db.get(DeliveryWindow, window_id)
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    return templates.TemplateResponse("admin_delivery_windows.html", {"request": request, "windows": windows, "window": window})


@router.post("/delivery-windows")
@router.post("/delivery-windows/{window_id}")
async def save_delivery_window(request: Request, db: Annotated[Session, Depends(get_db)], window_id: int | None = None):
    form = await request.form()
    window = db.get(DeliveryWindow, window_id) if window_id else DeliveryWindow()
    if not window:
        raise HTTPException(status_code=404, detail="Delivery window not found")
    window.name = _required_text(form.get("name"), "name")
    window.region = _optional(form.get("region"))
    window.delivery_date = _optional_datetime(form.get("delivery_date"))
    window.start_time = _optional(form.get("start_time"))
    window.end_time = _optional(form.get("end_time"))
    window.max_orders = _int(form.get("max_orders"), 40)
    window.current_order_count = _int(form.get("current_order_count"), 0)
    window.active = form.get("active") == "on"
    window.notes = _optional(form.get("notes"))
    db.add(window)
    db.commit()
    return RedirectResponse("/admin/delivery-windows", status_code=303)


@router.get("/routes")
def list_routes(request: Request, db: Annotated[Session, Depends(get_db)]):
    routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
    drivers = db.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name, Driver.first_name)).all()
    suggestions = route_driver_suggestions(db, routes)
    return templates.TemplateResponse("admin_routes.html", {"request": request, "routes": routes, "drivers": drivers, "suggestions": suggestions, "route_progress": route_progress})


@router.get("/routes/new")
def new_route(request: Request, db: Annotated[Session, Depends(get_db)]):
    drivers = db.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name)).all()
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    return templates.TemplateResponse("admin_route_form.html", {"request": request, "route": None, "drivers": drivers, "windows": windows})


@router.get("/routes/{route_id}")
def edit_route(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    for stop in route.stops:
        sync_stop_from_order(stop)
    refresh_route_estimates(route)
    ensure_route_payout(db, route)
    db.commit()
    drivers = db.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name)).all()
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date.desc())).all()
    orders = db.scalars(select(Order).where(Order.route_id.is_(None), Order.order_status.in_(["confirmed", "packed", "assigned_to_route"])).order_by(Order.created_at)).all()
    return templates.TemplateResponse(
        "admin_route_detail.html",
        {
            "request": request,
            "route": route,
            "drivers": drivers,
            "windows": windows,
            "orders": orders,
            "progress": route_progress(route),
            "order_summary": order_summary,
            "suggestion": route_driver_suggestions(db, [route]).get(route.id),
        },
    )


@router.post("/routes")
@router.post("/routes/{route_id}")
async def save_route(request: Request, db: Annotated[Session, Depends(get_db)], route_id: int | None = None):
    form = await request.form()
    route = db.get(Route, route_id) if route_id else Route()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    route.route_name = _required_text(form.get("route_name"), "route_name")
    route.delivery_window_id = _optional_int(form.get("delivery_window_id"))
    route.driver_id = _optional_int(form.get("driver_id"))
    route.region = _optional(form.get("region"))
    route.route_status = str(form.get("route_status") or "planned")
    route.estimated_start_time = _optional(form.get("estimated_start_time"))
    route.estimated_end_time = _optional(form.get("estimated_end_time"))
    route.estimated_stop_count = _int(form.get("estimated_stop_count"), route.estimated_stop_count or 0)
    route.estimated_order_count = _int(form.get("estimated_order_count"), route.estimated_order_count or 0)
    route.route_pay = _float(form.get("route_pay"), 0.0)
    route.route_bonus = _float(form.get("route_bonus"), 0.0)
    route.route_notes = _optional(form.get("route_notes"))
    route.notes = _optional(form.get("notes"))
    db.add(route)
    db.flush()
    ensure_route_payout(db, route)
    db.commit()
    return RedirectResponse(f"/admin/routes/{route.id}", status_code=303)


@router.post("/routes/suggestions/accept-all")
def accept_all_route_suggestions(db: Annotated[Session, Depends(get_db)]):
    suggestions = route_driver_suggestions(db)
    for route_id, suggestion in suggestions.items():
        route = db.get(Route, route_id)
        best = suggestion.get("best")
        if route and best:
            assign_route_to_driver(db, route, best["driver"].id)
    db.commit()
    return RedirectResponse("/admin/routes", status_code=303)


@router.post("/routes/{route_id}/suggestions/accept")
def accept_route_suggestion(route_id: int, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    suggestion = route_driver_suggestions(db, [route]).get(route.id)
    best = suggestion.get("best") if suggestion else None
    if best:
        assign_route_to_driver(db, route, best["driver"].id)
        db.commit()
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)


@router.post("/routes/{route_id}/assign-driver")
async def assign_driver_manually(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    form = await request.form()
    assign_route_to_driver(db, route, _optional_int(form.get("driver_id")))
    db.commit()
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)


@router.post("/routes/{route_id}/stops")
async def add_route_stop(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    form = await request.form()
    order_id = _required_int(form.get("order_id"), "order_id")
    if db.scalars(select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.order_id == order_id)).first():
        return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)
    max_sequence = db.scalar(select(func.coalesce(func.max(RouteStop.stop_sequence), 0)).where(RouteStop.route_id == route_id))
    order = db.get(Order, order_id)
    stop = RouteStop(route_id=route_id, order_id=order_id, stop_sequence=max_sequence + 1, stop_status="pending")
    db.add(stop)
    db.flush()
    if order:
        order.route_id = route_id
        order.order_status = "assigned_to_route"
        sync_stop_from_order(stop)
    refresh_route_estimates(route)
    ensure_route_payout(db, route)
    db.commit()
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)


@router.post("/routes/{route_id}/stops/{stop_id}")
async def update_route_stop(route_id: int, stop_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    stop = db.get(RouteStop, stop_id)
    form = await request.form()
    if stop:
        stop.stop_sequence = _int(form.get("stop_sequence"), stop.stop_sequence)
        stop.stop_status = str(form.get("stop_status") or stop.stop_status)
        stop.delivery_notes = _optional(form.get("delivery_notes"))
        stop.driver_notes = _optional(form.get("driver_notes"))
        stop.failed_reason = _optional(form.get("failed_reason"))
        sync_stop_from_order(stop)
        if stop.route:
            refresh_route_estimates(stop.route)
            ensure_route_payout(db, stop.route)
        db.commit()
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)


@router.post("/routes/{route_id}/payout")
async def update_route_payout(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    form = await request.form()
    payout = ensure_route_payout(db, route)
    payout.tip_amount = _float(form.get("tip_amount"), payout.tip_amount or 0.0)
    payout.payout_status = str(form.get("payout_status") or payout.payout_status)
    payout.payout_notes = _optional(form.get("payout_notes"))
    payout.total_pay = round((payout.base_route_pay or 0.0) + (payout.bonus_pay or 0.0) + (payout.tip_amount or 0.0), 2)
    db.commit()
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=303)


@router.get("/exports")
def exports_page(request: Request):
    return templates.TemplateResponse("admin_exports.html", {"request": request})


@router.get("/exports/{export_type}")
def export_operational_data(export_type: str, db: Annotated[Session, Depends(get_db)]):
    exporters = {
        "orders": lambda: orders_to_excel(db),
        "routes": lambda: routes_to_excel(db),
        "route-manifest": lambda: route_manifest_to_excel(db),
        "delivery-summary": lambda: delivery_summary_to_excel(db),
        "driver-payouts": lambda: driver_payouts_to_excel(db),
        "completed-routes": lambda: completed_routes_to_excel(db),
        "failed-deliveries": lambda: delivery_summary_to_excel(db, "failed"),
        "producers": lambda: producers_to_excel(db),
        "products": lambda: products_to_excel(db),
        "delivery-windows": lambda: delivery_windows_to_excel(db),
        "customers": lambda: customers_to_excel(db),
        "drivers": lambda: drivers_to_excel(db),
    }
    if export_type not in exporters:
        raise HTTPException(status_code=404, detail="Export not found")
    return StreamingResponse(
        exporters[export_type](),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="farmsource-{export_type}.xlsx"'},
    )


@router.get("/categories")
def list_categories(request: Request, db: Annotated[Session, Depends(get_db)]):
    categories = db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    return templates.TemplateResponse("admin_categories.html", {"request": request, "categories": categories})


@router.post("/categories")
async def create_category(request: Request, db: Annotated[Session, Depends(get_db)]):
    form = await request.form()
    category = ProductCategory(
        name=str(form.get("name") or "").strip(),
        description=_optional(form.get("description")),
        active=form.get("active") == "on",
    )
    if not category.name:
        raise HTTPException(status_code=400, detail="Category name is required")
    db.add(category)
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/categories/{category_id}")
async def update_category(category_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    category = db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    form = await request.form()
    category.name = str(form.get("name") or "").strip()
    category.description = _optional(form.get("description"))
    category.active = form.get("active") == "on"
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.get("/products")
def list_products(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    producer_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
):
    query = _filtered_product_query(producer_id, category_id, status)
    products = db.scalars(query.order_by(Product.name)).all()
    producers = db.scalars(select(Producer).order_by(Producer.producer_name)).all()
    categories = db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    return templates.TemplateResponse(
        "admin_products.html",
        {
            "request": request,
            "products": products,
            "producers": producers,
            "categories": categories,
            "filters": {"producer_id": producer_id, "category_id": category_id, "status": status or ""},
        },
    )


@router.get("/products/new")
def new_product(request: Request, db: Annotated[Session, Depends(get_db)]):
    return _product_form_response(request, db, Product(active=True, delivery_eligible=True, unit="each"))


@router.get("/products/export")
def export_products(
    db: Annotated[Session, Depends(get_db)],
    producer_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
):
    output = products_to_excel(db, _filtered_product_query(producer_id, category_id, status).order_by(Product.name))
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="farmsource-products.xlsx"'},
    )


@router.get("/availability/export")
def export_availability(db: Annotated[Session, Depends(get_db)], low_inventory: bool = False):
    query = select(ProductAvailability).join(Product).order_by(Product.name)
    if low_inventory:
        query = query.where(
            ProductAvailability.status == "active",
            ProductAvailability.available_quantity > ProductAvailability.reserved_quantity,
            (ProductAvailability.available_quantity - ProductAvailability.reserved_quantity) <= LOW_INVENTORY_THRESHOLD,
        )
    output = availability_to_excel(db, query)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="farmsource-product-availability.xlsx"'},
    )


@router.post("/products")
async def create_product(request: Request, db: Annotated[Session, Depends(get_db)]):
    product = Product()
    await _apply_product_form(product, request)
    db.add(product)
    db.flush()
    _sync_product_images(db, product, await request.form())
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@router.get("/products/{product_id}")
def edit_product(product_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_form_response(request, db, product)


@router.post("/products/{product_id}")
async def update_product(product_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    form = await request.form()
    _apply_product_form_from_form(product, form)
    _sync_product_images(db, product, form)
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@router.post("/products/{product_id}/deactivate")
def deactivate_product(product_id: int, db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.active = False
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@router.get("/availability")
def manage_availability(request: Request, db: Annotated[Session, Depends(get_db)]):
    availability = db.scalars(
        select(ProductAvailability)
        .join(Product)
        .order_by(Product.name, ProductAvailability.id)
    ).all()
    products = db.scalars(select(Product).order_by(Product.name)).all()
    windows = db.scalars(select(DeliveryWindow).order_by(DeliveryWindow.delivery_date, DeliveryWindow.name)).all()
    low_inventory = low_inventory_availability(db)
    return templates.TemplateResponse(
        "admin_availability.html",
        {
            "request": request,
            "availability": availability,
            "products": products,
            "windows": windows,
            "low_inventory": low_inventory,
        },
    )


@router.post("/availability")
async def create_availability(request: Request, db: Annotated[Session, Depends(get_db)]):
    form = await request.form()
    availability = ProductAvailability(
        product_id=_required_int(form.get("product_id"), "product_id"),
        delivery_window_id=_optional_int(form.get("delivery_window_id")),
        available_quantity=_int(form.get("available_quantity"), 0),
        reserved_quantity=_int(form.get("reserved_quantity"), 0),
        status=str(form.get("status") or "active"),
    )
    db.add(availability)
    db.commit()
    return RedirectResponse("/admin/availability", status_code=303)


@router.post("/availability/{availability_id}")
async def update_availability(availability_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    availability = db.get(ProductAvailability, availability_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Availability not found")
    form = await request.form()
    availability.available_quantity = _int(form.get("available_quantity"), 0)
    availability.reserved_quantity = _int(form.get("reserved_quantity"), 0)
    availability.status = str(form.get("status") or "active")
    db.commit()
    return RedirectResponse("/admin/availability", status_code=303)


@router.get("/sources")
def list_sources(request: Request, db: Annotated[Session, Depends(get_db)]):
    sources = db.scalars(select(Source).order_by(Source.source_name)).all()
    return templates.TemplateResponse("admin_sources.html", {"request": request, "sources": sources})


@router.get("/sources/new")
def new_source(request: Request):
    return templates.TemplateResponse("admin_source_form.html", {"request": request, "source": None})


@router.post("/sources")
async def create_source(request: Request, db: Annotated[Session, Depends(get_db)]):
    form = await request.form()
    source = Source(
        source_name=str(form.get("source_name") or "").strip(),
        source_type=_optional(form.get("source_type")),
        source_url=_optional(form.get("source_url")),
        region=_optional(form.get("region")),
        state=_optional(form.get("state")),
        enabled=form.get("enabled") == "on",
        notes=_optional(form.get("notes")),
    )
    if not source.source_name:
        raise HTTPException(status_code=400, detail="source_name is required")
    db.add(source)
    db.commit()
    return RedirectResponse("/admin/sources", status_code=303)


@router.get("/sources/{source_id}/edit")
def edit_source(source_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return templates.TemplateResponse("admin_source_form.html", {"request": request, "source": source})


@router.post("/sources/{source_id}")
async def update_source(source_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    form = await request.form()
    source.source_name = str(form.get("source_name") or "").strip()
    source.source_type = _optional(form.get("source_type"))
    source.source_url = _optional(form.get("source_url"))
    source.region = _optional(form.get("region"))
    source.state = _optional(form.get("state"))
    source.enabled = form.get("enabled") == "on"
    source.notes = _optional(form.get("notes"))
    db.commit()
    return RedirectResponse("/admin/sources", status_code=303)


@router.get("/imports")
def import_form(request: Request, db: Annotated[Session, Depends(get_db)], import_run_id: int | None = None):
    sources = db.scalars(select(Source).order_by(Source.source_name)).all()
    import_run = db.get(ImportRun, import_run_id) if import_run_id else None
    recent_runs = db.scalars(select(ImportRun).order_by(ImportRun.created_at.desc()).limit(10)).all()
    return templates.TemplateResponse(
        "admin_import.html",
        {"request": request, "sources": sources, "import_run": import_run, "recent_runs": recent_runs},
    )


@router.post("/imports")
async def import_csv(
    db: Annotated[Session, Depends(get_db)],
    source_id: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile, File()] = None,
):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="CSV file is required")
    content = await file.read()
    summary = import_producers_from_csv(db, _optional_int(source_id), file.filename, content)
    return RedirectResponse(f"/admin/imports?import_run_id={summary.import_run_id}", status_code=303)


@router.get("/producers")
def list_producers(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    source_id: int | None = None,
    city: str | None = None,
    state: str | None = None,
    product: str | None = None,
    online_ordering_status: str | None = None,
):
    query = _filtered_producer_query(source_id, city, state, product, online_ordering_status)
    producers = db.scalars(query.order_by(Producer.producer_name).limit(500)).all()
    sources = db.scalars(select(Source).order_by(Source.source_name)).all()
    return templates.TemplateResponse(
        "admin_producers.html",
        {
            "request": request,
            "producers": producers,
            "sources": sources,
            "filters": {
                "source_id": source_id,
                "city": city or "",
                "state": state or "",
                "product": product or "",
                "online_ordering_status": online_ordering_status or "",
            },
        },
    )


@router.get("/producers/{producer_id}/edit")
def edit_producer(producer_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    producer = db.get(Producer, producer_id)
    if not producer:
        raise HTTPException(status_code=404, detail="Producer not found")
    sources = db.scalars(select(Source).order_by(Source.source_name)).all()
    return templates.TemplateResponse(
        "admin_producer_form.html",
        {"request": request, "producer": producer, "sources": sources},
    )


@router.post("/producers/{producer_id}")
async def update_producer(producer_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    producer = db.get(Producer, producer_id)
    if not producer:
        raise HTTPException(status_code=404, detail="Producer not found")
    form = await request.form()
    for field in (
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
        "contact_email",
        "contact_phone",
        "notes",
    ):
        setattr(producer, field, _optional(form.get(field)))
    producer.source_id = _optional_int(form.get("source_id"))
    producer.delivery_available = form.get("delivery_available") == "on"
    producer.pickup_available = form.get("pickup_available") == "on"
    producer.qualified = form.get("qualified") == "on"

    classification = classify_producer_destination(producer.website_url, producer.online_order_url)
    producer.destination_type = classification.destination_type
    producer.platform_detected = classification.platform_detected
    producer.confidence_score = classification.confidence_score
    producer.online_ordering_confirmed = classification.online_ordering_confirmed
    producer.classification_reason = classification.reason
    if not producer.online_ordering_confirmed:
        producer.qualified = False

    db.commit()
    return RedirectResponse("/admin/producers", status_code=303)


@router.post("/producers/{producer_id}/qualification")
async def update_qualification(
    producer_id: int,
    db: Annotated[Session, Depends(get_db)],
    qualified: Annotated[str, Form()],
):
    producer = db.get(Producer, producer_id)
    if not producer:
        raise HTTPException(status_code=404, detail="Producer not found")
    producer.qualified = qualified == "true"
    db.commit()
    return RedirectResponse("/admin/producers", status_code=303)


@router.get("/producers/export")
def export_producers(
    db: Annotated[Session, Depends(get_db)],
    source_id: int | None = None,
    city: str | None = None,
    state: str | None = None,
    product: str | None = None,
    online_ordering_status: str | None = None,
    qualified_only: bool = False,
):
    query = _filtered_producer_query(source_id, city, state, product, online_ordering_status)
    if qualified_only:
        query = query.where(Producer.qualified.is_(True))
    output = producers_to_excel(db, query.order_by(Producer.producer_name))
    headers = {"Content-Disposition": 'attachment; filename="farmsource-producers.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def _filtered_producer_query(
    source_id: int | None,
    city: str | None,
    state: str | None,
    product: str | None,
    online_ordering_status: str | None,
):
    query = select(Producer)
    if source_id:
        query = query.where(Producer.source_id == source_id)
    if city:
        query = query.where(Producer.city.ilike(f"%{city}%"))
    if state:
        query = query.where(Producer.state.ilike(f"%{state}%"))
    if product:
        query = query.where(Producer.products.ilike(f"%{product}%"))
    if online_ordering_status == "confirmed":
        query = query.where(Producer.online_ordering_confirmed.is_(True))
    elif online_ordering_status == "not_confirmed":
        query = query.where(Producer.online_ordering_confirmed.is_(False))
    elif online_ordering_status == "qualified":
        query = query.where(Producer.qualified.is_(True))
    elif online_ordering_status == "not_qualified":
        query = query.where(Producer.qualified.is_(False))
    return query


def _filtered_product_query(
    producer_id: int | None,
    category_id: int | None,
    status: str | None,
):
    query = select(Product)
    if producer_id:
        query = query.where(Product.producer_id == producer_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if status == "active":
        query = query.where(Product.active.is_(True))
    elif status == "inactive":
        query = query.where(Product.active.is_(False))
    elif status == "featured":
        query = query.where(Product.featured.is_(True))
    elif status == "seasonal":
        query = query.where(Product.seasonal.is_(True))
    return query


def _filtered_order_query(
    status: str | None,
    delivery_window_id: int | None,
    route_id: int | None,
    customer: str | None,
):
    query = select(Order).join(Customer)
    if status:
        query = query.where(Order.order_status == status)
    if delivery_window_id:
        query = query.where(Order.delivery_window_id == delivery_window_id)
    if route_id:
        query = query.where(Order.route_id == route_id)
    if customer:
        query = query.where(
            (Customer.email.ilike(f"%{customer}%"))
            | (Customer.first_name.ilike(f"%{customer}%"))
            | (Customer.last_name.ilike(f"%{customer}%"))
        )
    return query


def _product_form_response(request: Request, db: Session, product: Product):
    producers = db.scalars(select(Producer).order_by(Producer.producer_name)).all()
    categories = db.scalars(select(ProductCategory).where(ProductCategory.active.is_(True)).order_by(ProductCategory.name)).all()
    return templates.TemplateResponse(
        "admin_product_form.html",
        {"request": request, "product": product, "producers": producers, "categories": categories},
    )


async def _apply_product_form(product: Product, request: Request) -> None:
    form = await request.form()
    _apply_product_form_from_form(product, form)


def _apply_product_form_from_form(product: Product, form) -> None:
    product.producer_id = _optional_int(form.get("producer_id"))
    product.category_id = _optional_int(form.get("category_id"))
    product.name = str(form.get("name") or "").strip()
    if not product.name:
        raise HTTPException(status_code=400, detail="Product name is required")
    product.short_description = _optional(form.get("short_description"))
    product.full_description = _optional(form.get("full_description"))
    product.sku = _optional(form.get("sku"))
    product.unit = _optional(form.get("unit")) or "each"
    product.price = _float(form.get("price"), 0.0)
    product.compare_at_price = _optional_float(form.get("compare_at_price"))
    product.image_url = _optional(form.get("image_url"))
    product.featured = form.get("featured") == "on"
    product.active = form.get("active") == "on"
    product.seasonal = form.get("seasonal") == "on"
    product.delivery_eligible = form.get("delivery_eligible") == "on"


def _sync_product_images(db: Session, product: Product, form) -> None:
    for image in list(product.images):
        db.delete(image)
    image_urls = [_optional(form.get("image_url")), _optional(form.get("image_url_2")), _optional(form.get("image_url_3"))]
    for sort_order, image_url in enumerate([url for url in image_urls if url]):
        db.add(ProductImage(product_id=product.id, image_url=image_url, sort_order=sort_order))


def _optional(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _optional_int(value) -> int | None:
    value = _optional(value)
    return int(value) if value else None


def _required_int(value, field_name: str) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return parsed


def _required_text(value, field_name: str) -> str:
    value = _optional(value)
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return value


def _optional_datetime(value) -> datetime | None:
    value = _optional(value)
    if not value:
        return None
    return datetime.fromisoformat(value)


def _int(value, default: int) -> int:
    value = _optional(value)
    return int(value) if value else default


def _float(value, default: float) -> float:
    value = _optional(value)
    return float(value) if value else default


def _optional_float(value) -> float | None:
    value = _optional(value)
    return float(value) if value else None
