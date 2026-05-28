import csv
from datetime import datetime
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR, get_settings
from app.database import get_db
from app.models import (
    Customer,
    DeliveryWindow,
    Driver,
    DriverInterest,
    DriverPayout,
    ImportRun,
    MarketingContent,
    MarketingContentAsset,
    MarketingContentSchedule,
    Order,
    Producer,
    ProducerInterest,
    ProducerOutreachCandidate,
    Product,
    ProductAvailability,
    ProductCategory,
    ProductImage,
    Route,
    RouteStop,
    Source,
    WaitlistSignup,
)
from app.services.auth import hash_password, require_admin
from app.services.catalog import LOW_INVENTORY_THRESHOLD, low_inventory_availability
from app.services.classification import classify_producer_destination
from app.services.csv_importer import import_producers_from_csv
from app.services.delivery import assign_route_to_driver, ensure_route_payout, order_summary, refresh_route_estimates, route_driver_suggestions, route_progress, sync_stop_from_order
from app.services.exporter import availability_to_excel, completed_routes_to_excel, customers_to_excel, delivery_summary_to_excel, delivery_windows_to_excel, driver_interests_to_excel, driver_payouts_to_excel, drivers_to_excel, marketing_content_to_excel, orders_to_excel, producer_interests_to_excel, producers_to_excel, products_to_excel, route_manifest_to_excel, routes_to_excel, waitlist_to_excel
from app.services.outreach import COMPLETED_RESEARCH_STATUSES, LOCKED_RESEARCH_STATUSES, OUTREACH_STATUSES, REGION_PROFILES, RESEARCH_STATUSES, generate_outreach_email, normalize_outreach_csv, research_candidate_now, research_next_candidates
from app.services.ai_services.content_generator import CONTENT_STATUSES, CONTENT_TYPES, POSTING_STATUSES, TARGET_AUDIENCES, TARGET_PLATFORMS, generate_marketing_content


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


@router.get("/drivers/interests")
def admin_driver_interests(request: Request, db: Annotated[Session, Depends(get_db)]):
    interests = db.scalars(select(DriverInterest).order_by(DriverInterest.created_at.desc())).all()
    return templates.TemplateResponse("admin_driver_interests.html", {"request": request, "interests": interests})


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


@router.get("/waitlist")
def admin_waitlist(request: Request, db: Annotated[Session, Depends(get_db)], signup_type: str | None = None):
    query = select(WaitlistSignup)
    if signup_type:
        query = query.where(WaitlistSignup.signup_type == signup_type)
    signups = db.scalars(query.order_by(WaitlistSignup.created_at.desc())).all()
    return templates.TemplateResponse("admin_waitlist.html", {"request": request, "signups": signups, "signup_type": signup_type or ""})


@router.get("/producers/interests")
def admin_producer_interests(request: Request, db: Annotated[Session, Depends(get_db)]):
    interests = db.scalars(select(ProducerInterest).order_by(ProducerInterest.created_at.desc())).all()
    return templates.TemplateResponse("admin_producer_interests.html", {"request": request, "interests": interests})


@router.get("/marketing")
def marketing_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    content_type: str | None = None,
    audience: str | None = None,
    platform: str | None = None,
    status: str | None = None,
):
    query = _filtered_marketing_query(content_type, audience, platform, status)
    contents = db.scalars(query.order_by(MarketingContent.created_at.desc())).all()
    scheduled = db.scalars(select(MarketingContentSchedule).order_by(MarketingContentSchedule.scheduled_date.asc()).limit(20)).all()
    return templates.TemplateResponse(
        "admin_marketing.html",
        {
            "request": request,
            "contents": contents,
            "scheduled": scheduled,
            "filters": {"content_type": content_type or "", "audience": audience or "", "platform": platform or "", "status": status or ""},
            "content_types": CONTENT_TYPES,
            "target_audiences": TARGET_AUDIENCES,
            "target_platforms": TARGET_PLATFORMS,
            "content_statuses": CONTENT_STATUSES,
            "draft_count": db.scalar(select(func.count(MarketingContent.id)).where(MarketingContent.status.in_(["draft", "generated", "ready_for_review"]))),
            "approved_count": db.scalar(select(func.count(MarketingContent.id)).where(MarketingContent.status == "approved")),
            "scheduled_count": db.scalar(select(func.count(MarketingContentSchedule.id)).where(MarketingContentSchedule.posting_status.in_(["planned", "pending"]))),
        },
    )


@router.get("/marketing/new")
def new_marketing_content(request: Request):
    return templates.TemplateResponse(
        "admin_marketing_form.html",
        {
            "request": request,
            "content": MarketingContent(content_type="produce_box", target_platform="instagram", target_audience="customers", status="draft"),
            "content_types": CONTENT_TYPES,
            "target_audiences": TARGET_AUDIENCES,
            "target_platforms": TARGET_PLATFORMS,
            "content_statuses": CONTENT_STATUSES,
        },
    )


@router.post("/marketing")
async def create_marketing_content(request: Request, db: Annotated[Session, Depends(get_db)]):
    form = await request.form()
    content = MarketingContent()
    _apply_marketing_form(content, form)
    if form.get("generate") == "on":
        _generate_marketing_fields(content)
    db.add(content)
    db.flush()
    _sync_marketing_schedule(db, content)
    _add_marketing_asset(db, content, form)
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


@router.get("/marketing/calendar")
def marketing_calendar(request: Request, db: Annotated[Session, Depends(get_db)]):
    schedules = db.scalars(select(MarketingContentSchedule).order_by(MarketingContentSchedule.scheduled_date.asc())).all()
    drafts = db.scalars(select(MarketingContent).where(MarketingContent.status.in_(["draft", "generated", "ready_for_review"])).order_by(MarketingContent.created_at.desc()).limit(25)).all()
    approved = db.scalars(select(MarketingContent).where(MarketingContent.status == "approved").order_by(MarketingContent.updated_at.desc()).limit(25)).all()
    return templates.TemplateResponse("admin_marketing_calendar.html", {"request": request, "schedules": schedules, "drafts": drafts, "approved": approved})


@router.get("/marketing/drafts")
def marketing_drafts(request: Request, db: Annotated[Session, Depends(get_db)]):
    contents = db.scalars(
        select(MarketingContent)
        .where(MarketingContent.status.in_(["draft", "generated", "ready_for_review", "rejected"]))
        .order_by(MarketingContent.created_at.desc())
    ).all()
    return templates.TemplateResponse("admin_marketing_drafts.html", {"request": request, "contents": contents})


@router.get("/marketing/{content_id}")
def edit_marketing_content(content_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    return templates.TemplateResponse(
        "admin_marketing_form.html",
        {
            "request": request,
            "content": content,
            "content_types": CONTENT_TYPES,
            "target_audiences": TARGET_AUDIENCES,
            "target_platforms": TARGET_PLATFORMS,
            "content_statuses": CONTENT_STATUSES,
            "posting_statuses": POSTING_STATUSES,
        },
    )


@router.post("/marketing/{content_id}")
async def update_marketing_content(content_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    form = await request.form()
    _apply_marketing_form(content, form)
    if form.get("generate") == "on":
        _generate_marketing_fields(content)
    _sync_marketing_schedule(db, content)
    _add_marketing_asset(db, content, form)
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


@router.post("/marketing/{content_id}/generate")
def generate_marketing_draft(content_id: int, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    _generate_marketing_fields(content)
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


@router.post("/marketing/{content_id}/approve")
def approve_marketing_draft(content_id: int, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    content.status = "approved"
    content.approved = True
    _sync_marketing_schedule(db, content)
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


@router.post("/marketing/{content_id}/reject")
def reject_marketing_draft(content_id: int, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    content.status = "rejected"
    content.approved = False
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


@router.post("/marketing/{content_id}/mark-posted")
def mark_marketing_posted(content_id: int, db: Annotated[Session, Depends(get_db)]):
    content = db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Marketing content not found")
    content.status = "posted"
    for schedule in content.schedules:
        schedule.posting_status = "posted"
    db.commit()
    return RedirectResponse(f"/admin/marketing/{content.id}", status_code=303)


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
    routes = db.scalars(select(Route).order_by(Route.reassignment_priority.desc(), Route.created_at.desc())).all()
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
    route.reassignment_priority = form.get("reassignment_priority") == "on"
    route.assignment_notes = _optional(form.get("assignment_notes"))
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


@router.post("/routes/{route_id}/unassign-driver")
def unassign_route_driver(route_id: int, db: Annotated[Session, Depends(get_db)]):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    assign_route_to_driver(db, route, None)
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
        "waitlist": lambda: waitlist_to_excel(db),
        "producer-interests": lambda: producer_interests_to_excel(db),
        "driver-interests": lambda: driver_interests_to_excel(db),
        "marketing-content": lambda: marketing_content_to_excel(db),
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


@router.get("/outreach")
def outreach_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    region: str = "seattle",
    status: str | None = None,
    research_status: str | None = None,
    summary: str | None = None,
):
    query = select(ProducerOutreachCandidate).where(ProducerOutreachCandidate.region == region)
    if status:
        query = query.where(ProducerOutreachCandidate.outreach_status == status)
    if research_status:
        query = query.where(ProducerOutreachCandidate.research_status == research_status)
    candidates = db.scalars(
        query.order_by(ProducerOutreachCandidate.priority_rank, ProducerOutreachCandidate.priority_score.desc()).limit(250)
    ).all()
    status_counts = db.execute(
        select(ProducerOutreachCandidate.outreach_status, func.count(ProducerOutreachCandidate.id))
        .where(ProducerOutreachCandidate.region == region)
        .group_by(ProducerOutreachCandidate.outreach_status)
    ).all()
    progress = _outreach_progress(db, region)
    return templates.TemplateResponse(
        "admin_outreach.html",
        {
            "request": request,
            "candidates": candidates,
            "regions": REGION_PROFILES,
            "selected_region": region,
            "outreach_statuses": OUTREACH_STATUSES,
            "research_statuses": RESEARCH_STATUSES,
            "filters": {"status": status or "", "research_status": research_status or ""},
            "summary": summary,
            "status_counts": status_counts,
            "progress": progress,
            "local_research_enabled": _local_research_enabled(),
        },
    )


@router.post("/outreach/import")
async def import_outreach_csv(
    db: Annotated[Session, Depends(get_db)],
    source_name: Annotated[str, Form()] = "",
    region: Annotated[str, Form()] = "seattle",
    active_status_only: Annotated[str | None, Form()] = None,
    state_filter: Annotated[str | None, Form()] = None,
    clear_existing_region: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile, File()] = None,
):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="CSV file is required")
    if region not in REGION_PROFILES:
        raise HTTPException(status_code=400, detail="Unsupported region")
    content = await file.read()
    summary = normalize_outreach_csv(
        db,
        content=content,
        filename=file.filename,
        source_name=source_name or file.filename,
        region=region,
        active_status_only=active_status_only == "on",
        state_filter=_optional(state_filter),
        clear_existing_region=clear_existing_region == "on",
    )
    message = (
        f"Imported {summary.imported_rows} producers and created {summary.candidate_count} ranked outreach candidates "
        f"for {REGION_PROFILES[region]['label']}."
    )
    return RedirectResponse(f"/admin/outreach?region={region}&summary={message}", status_code=303)


@router.get("/outreach/progress")
def outreach_progress(db: Annotated[Session, Depends(get_db)], region: str = "seattle"):
    return _outreach_progress(db, region)


@router.get("/outreach/updates")
def outreach_updates(
    db: Annotated[Session, Depends(get_db)],
    region: str = "seattle",
    status: str | None = None,
    research_status: str | None = None,
):
    query = select(ProducerOutreachCandidate).where(ProducerOutreachCandidate.region == region)
    if status:
        query = query.where(ProducerOutreachCandidate.outreach_status == status)
    if research_status:
        query = query.where(ProducerOutreachCandidate.research_status == research_status)
    candidates = db.scalars(
        query.order_by(ProducerOutreachCandidate.priority_rank, ProducerOutreachCandidate.priority_score.desc()).limit(250)
    ).all()
    return {"progress": _outreach_progress(db, region), "candidates": [_candidate_payload(candidate) for candidate in candidates]}


@router.get("/outreach/candidates/{candidate_id}")
def outreach_candidate_detail(candidate_id: int, db: Annotated[Session, Depends(get_db)]):
    candidate = db.get(ProducerOutreachCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Outreach candidate not found")
    return {"candidate": _candidate_payload(candidate), "progress": _outreach_progress(db, candidate.region)}


@router.get("/outreach/candidates/{candidate_id}/email-suggestion")
def outreach_email_suggestion(candidate_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    candidate = db.get(ProducerOutreachCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Outreach candidate not found")
    if not candidate.contact_email:
        raise HTTPException(status_code=400, detail="Candidate does not have an email address")
    email = generate_outreach_email(candidate)
    return templates.TemplateResponse(
        "admin_outreach_email.html",
        {"request": request, "candidate": candidate, "email": email},
    )


@router.post("/outreach/candidates/{candidate_id}/research")
def request_outreach_research(candidate_id: int, db: Annotated[Session, Depends(get_db)]):
    _require_local_research()
    candidate = db.get(ProducerOutreachCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Outreach candidate not found")
    already_completed = candidate.research_status in LOCKED_RESEARCH_STATUSES
    research_candidate_now(candidate)
    if candidate.producer_id:
        producer = db.get(Producer, candidate.producer_id)
        if producer:
            producer.website_url = candidate.website_url or producer.website_url
            producer.contact_email = candidate.contact_email or producer.contact_email
            producer.contact_phone = candidate.contact_phone or producer.contact_phone
            producer.instagram_url = candidate.instagram_url or producer.instagram_url
            producer.facebook_url = candidate.facebook_url or producer.facebook_url
            producer.notes = candidate.notes or producer.notes
    db.commit()
    db.refresh(candidate)
    return {
        "candidate": _candidate_payload(candidate),
        "progress": _outreach_progress(db, candidate.region),
        "already_completed": already_completed,
    }


@router.post("/outreach/research-all")
def research_next_outreach_candidates(
    db: Annotated[Session, Depends(get_db)],
    region: Annotated[str, Form()] = "seattle",
    status: Annotated[str | None, Form()] = None,
    research_status: Annotated[str | None, Form()] = None,
):
    _require_local_research()
    candidates = research_next_candidates(db, region)
    db.commit()
    refreshed = db.scalars(
        select(ProducerOutreachCandidate)
        .where(ProducerOutreachCandidate.region == region)
        .order_by(ProducerOutreachCandidate.priority_rank, ProducerOutreachCandidate.priority_score.desc())
        .limit(250)
    ).all()
    return {
        "researched": len(candidates),
        "progress": _outreach_progress(db, region),
        "candidates": [_candidate_payload(candidate) for candidate in refreshed],
    }


@router.post("/outreach/candidates/{candidate_id}")
async def update_outreach_candidate(
    candidate_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    candidate = db.get(ProducerOutreachCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Outreach candidate not found")
    form = await request.form()
    candidate.outreach_status = str(form.get("outreach_status") or candidate.outreach_status)
    candidate.research_status = str(form.get("research_status") or candidate.research_status)
    candidate.website_url = _optional(form.get("website_url"))
    candidate.contact_email = _optional(form.get("contact_email"))
    candidate.contact_phone = _optional(form.get("contact_phone"))
    candidate.instagram_url = _optional(form.get("instagram_url"))
    candidate.facebook_url = _optional(form.get("facebook_url"))
    candidate.next_step = _optional(form.get("next_step"))
    candidate.notes = _optional(form.get("notes"))
    if candidate.producer_id:
        producer = db.get(Producer, candidate.producer_id)
        if producer:
            producer.website_url = candidate.website_url or producer.website_url
            producer.contact_email = candidate.contact_email or producer.contact_email
            producer.contact_phone = candidate.contact_phone or producer.contact_phone
            producer.instagram_url = candidate.instagram_url or producer.instagram_url
            producer.facebook_url = candidate.facebook_url or producer.facebook_url
    db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        db.refresh(candidate)
        return {"candidate": _candidate_payload(candidate), "progress": _outreach_progress(db, candidate.region)}
    return RedirectResponse(f"/admin/outreach?region={candidate.region}", status_code=303)


@router.get("/outreach/export")
def export_outreach_candidates(db: Annotated[Session, Depends(get_db)], region: str = "seattle"):
    output = StringIO()
    fieldnames = [
        "priority_rank",
        "priority_score",
        "producer_name",
        "city",
        "state",
        "zip_code",
        "producer_type",
        "ubi",
        "registered_agent",
        "principal_office_address",
        "website_url",
        "contact_email",
        "contact_phone",
        "instagram_url",
        "facebook_url",
        "outreach_status",
        "research_status",
        "search_url",
        "next_step",
        "priority_reason",
        "notes",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    rows = db.scalars(
        select(ProducerOutreachCandidate)
        .where(ProducerOutreachCandidate.region == region)
        .order_by(ProducerOutreachCandidate.priority_rank, ProducerOutreachCandidate.priority_score.desc())
    ).all()
    for candidate in rows:
        writer.writerow({field: getattr(candidate, field) for field in fieldnames})
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="farmsource-outreach-{region}.csv"'},
    )


def _outreach_progress(db: Session, region: str) -> dict:
    total = db.scalar(select(func.count(ProducerOutreachCandidate.id)).where(ProducerOutreachCandidate.region == region)) or 0
    researched = (
        db.scalar(
            select(func.count(ProducerOutreachCandidate.id)).where(
                ProducerOutreachCandidate.region == region,
                ProducerOutreachCandidate.research_status.in_(COMPLETED_RESEARCH_STATUSES),
            )
        )
        or 0
    )
    researching = (
        db.scalar(
            select(func.count(ProducerOutreachCandidate.id)).where(
                ProducerOutreachCandidate.region == region,
                ProducerOutreachCandidate.research_status.not_in(COMPLETED_RESEARCH_STATUSES),
            )
        )
        or 0
    )
    found_contact = (
        db.scalar(
            select(func.count(ProducerOutreachCandidate.id)).where(
                ProducerOutreachCandidate.region == region,
                ProducerOutreachCandidate.research_status == "found_contact",
            )
        )
        or 0
    )
    percent = round((researched / total) * 100, 1) if total else 0
    queued_percent = percent
    remaining = max(total - researched, 0)
    return {
        "region": region,
        "total": total,
        "researched": researched,
        "researching": researching,
        "found_contact": found_contact,
        "remaining": remaining,
        "percent": percent,
        "queued_percent": queued_percent,
    }


def _candidate_payload(candidate: ProducerOutreachCandidate) -> dict:
    return {
        "id": candidate.id,
        "priority_rank": candidate.priority_rank,
        "priority_score": candidate.priority_score,
        "producer_name": candidate.producer_name,
        "city": candidate.city,
        "state": candidate.state,
        "zip_code": candidate.zip_code,
        "producer_type": candidate.producer_type,
        "website_url": candidate.website_url,
        "contact_email": candidate.contact_email,
        "contact_phone": candidate.contact_phone,
        "instagram_url": candidate.instagram_url,
        "facebook_url": candidate.facebook_url,
        "outreach_status": candidate.outreach_status,
        "research_status": candidate.research_status,
        "search_url": candidate.search_url,
        "next_step": candidate.next_step,
        "notes": candidate.notes,
        "priority_reason": candidate.priority_reason,
    }


def _local_research_enabled() -> bool:
    return get_settings().app_env.lower() in {"local", "development", "dev", "test"}


def _require_local_research() -> None:
    if not _local_research_enabled():
        raise HTTPException(status_code=403, detail="Research queue actions are local-only.")


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


def _filtered_marketing_query(
    content_type: str | None,
    audience: str | None,
    platform: str | None,
    status: str | None,
):
    query = select(MarketingContent)
    if content_type:
        query = query.where(MarketingContent.content_type == content_type)
    if audience:
        query = query.where(MarketingContent.target_audience == audience)
    if platform:
        query = query.where(MarketingContent.target_platform == platform)
    if status:
        query = query.where(MarketingContent.status == status)
    return query


def _apply_marketing_form(content: MarketingContent, form) -> None:
    content.content_type = _optional(form.get("content_type")) or "produce_box"
    content.content_theme = _optional(form.get("content_theme")) or "fresh produce"
    content.title = _required_text(form.get("title"), "title")
    content.short_description = _optional(form.get("short_description"))
    content.ai_prompt = _optional(form.get("ai_prompt"))
    content.generated_caption = _optional(form.get("generated_caption"))
    content.generated_hashtags = _optional(form.get("generated_hashtags"))
    content.generated_video_prompt = _optional(form.get("generated_video_prompt"))
    content.generated_script = _optional(form.get("generated_script"))
    content.target_platform = _optional(form.get("target_platform")) or "instagram"
    content.target_audience = _optional(form.get("target_audience")) or "general"
    content.status = _optional(form.get("status")) or "draft"
    content.scheduled_date = _optional_datetime(form.get("scheduled_date"))
    content.approved = form.get("approved") == "on" or content.status == "approved"
    content.notes = _optional(form.get("notes"))
    if content.approved and content.status not in {"approved", "posted"}:
        content.status = "approved"


def _generate_marketing_fields(content: MarketingContent) -> None:
    generated = generate_marketing_content(
        content.content_type,
        content.content_theme,
        content.target_platform,
        content.target_audience,
        seed_title=content.title,
        notes=content.notes,
    )
    content.title = generated.title
    content.short_description = content.short_description or generated.short_description
    content.ai_prompt = generated.ai_prompt
    content.generated_caption = generated.generated_caption
    content.generated_hashtags = generated.generated_hashtags
    content.generated_video_prompt = generated.generated_video_prompt
    content.generated_script = generated.generated_script
    if content.status == "draft":
        content.status = "generated"


def _sync_marketing_schedule(db: Session, content: MarketingContent) -> None:
    if not content.scheduled_date:
        return
    schedule = content.schedules[0] if content.schedules else MarketingContentSchedule(marketing_content_id=content.id, scheduled_date=content.scheduled_date, posting_platform=content.target_platform)
    schedule.scheduled_date = content.scheduled_date
    schedule.posting_platform = content.target_platform
    if not schedule.posting_status:
        schedule.posting_status = "planned"
    db.add(schedule)


def _add_marketing_asset(db: Session, content: MarketingContent, form) -> None:
    asset_url = _optional(form.get("asset_url"))
    if not asset_url:
        return
    db.add(
        MarketingContentAsset(
            marketing_content_id=content.id,
            asset_type=_optional(form.get("asset_type")) or "reference",
            asset_url=asset_url,
        )
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
