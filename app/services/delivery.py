from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Driver, DriverPayout, Order, Route, RouteStop


ROUTE_STATUSES = {"planned", "assigned", "in_progress", "completed", "cancelled"}
STOP_STATUSES = {"pending", "delivered", "failed", "skipped"}
PAYOUT_STATUSES = {"pending", "approved", "paid"}


def order_summary(order: Order | None) -> str:
    if not order:
        return ""
    return ", ".join(f"{item.quantity} x {item.product.name if item.product else 'Item'}" for item in order.items)


def sync_stop_from_order(stop: RouteStop) -> None:
    order = stop.order
    if not order:
        return
    customer = order.customer
    stop.customer_name = (
        f"{customer.first_name} {customer.last_name}".strip()
        if customer
        else stop.customer_name
    )
    stop.address = order.delivery_address
    stop.city = order.delivery_city
    stop.state = order.delivery_state
    stop.zip_code = order.delivery_zip
    if not stop.delivery_notes:
        stop.delivery_notes = customer.delivery_notes if customer else order.customer_notes


def ensure_route_payout(db: Session, route: Route) -> DriverPayout:
    payout = route.payout
    if not payout:
        payout = DriverPayout(route_id=route.id, driver_id=route.driver_id)
        db.add(payout)
    payout.driver_id = route.driver_id
    payout.base_route_pay = route.route_pay or 0.0
    payout.bonus_pay = route.route_bonus or 0.0
    payout.total_pay = round((payout.base_route_pay or 0.0) + (payout.bonus_pay or 0.0) + (payout.tip_amount or 0.0), 2)
    return payout


def refresh_route_estimates(route: Route) -> None:
    route.estimated_stop_count = len(route.stops)
    route.estimated_order_count = len({stop.order_id for stop in route.stops})


def route_progress(route: Route) -> dict[str, int | float]:
    total = len(route.stops)
    completed = len([stop for stop in route.stops if stop.stop_status in {"delivered", "failed", "skipped"}])
    delivered = len([stop for stop in route.stops if stop.stop_status == "delivered"])
    failed = len([stop for stop in route.stops if stop.stop_status == "failed"])
    percent = round((completed / total) * 100, 1) if total else 0
    return {"total": total, "completed": completed, "delivered": delivered, "failed": failed, "percent": percent}


def update_stop_status(
    db: Session,
    stop: RouteStop,
    status: str,
    driver_notes: str | None = None,
    failed_reason: str | None = None,
    proof_of_delivery_url: str | None = None,
) -> None:
    if status not in STOP_STATUSES:
        raise ValueError("Invalid stop status")
    stop.stop_status = status
    stop.driver_notes = driver_notes
    stop.failed_reason = failed_reason
    stop.proof_of_delivery_url = proof_of_delivery_url
    if status == "delivered":
        stop.delivered_at = datetime.now(UTC)
        if stop.order:
            stop.order.order_status = "delivered"
    elif status == "failed":
        if stop.order:
            stop.order.order_status = "out_for_delivery"
    elif status == "skipped":
        if stop.order:
            stop.order.order_status = "assigned_to_route"

    route = stop.route
    if route:
        statuses = {route_stop.stop_status for route_stop in route.stops}
        if route.route_status == "planned":
            route.route_status = "in_progress"
        if statuses and statuses.issubset({"delivered", "failed", "skipped"}):
            route.route_status = "completed"
        elif route.route_status in {"planned", "assigned"}:
            route.route_status = "in_progress"
        refresh_route_estimates(route)
        ensure_route_payout(db, route)
    db.commit()


def assigned_driver_routes(db: Session, driver_id: int) -> list[Route]:
    return db.scalars(
        select(Route)
        .where(Route.driver_id == driver_id)
        .order_by(Route.created_at.desc())
    ).all()


def route_driver_suggestions(db: Session, routes: list[Route] | None = None) -> dict[int, dict]:
    if routes is None:
        routes = db.scalars(
            select(Route)
            .where(Route.route_status.in_(["planned", "assigned"]))
            .order_by(Route.created_at.desc())
        ).all()
    drivers = db.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name, Driver.first_name)).all()
    active_counts = dict(
        db.execute(
            select(Route.driver_id, func.count(Route.id))
            .where(Route.driver_id.is_not(None), Route.route_status.in_(["planned", "assigned", "in_progress"]))
            .group_by(Route.driver_id)
        ).all()
    )
    suggestions = {}
    for route in routes:
        ranked = sorted(
            (score_driver_for_route(driver, route, int(active_counts.get(driver.id, 0))) for driver in drivers),
            key=lambda item: item["score"],
            reverse=True,
        )
        best = ranked[0] if ranked else None
        suggestions[route.id] = {
            "route": route,
            "best": best,
            "ranked": ranked,
        }
    return suggestions


def score_driver_for_route(driver: Driver, route: Route, active_route_count: int) -> dict:
    score = 50
    reasons = []
    driver_territory = (driver.territory or "").strip().lower()
    route_region = (route.region or "").strip().lower()
    if driver_territory and route_region and driver_territory == route_region:
        score += 35
        reasons.append("territory match")
    elif driver_territory and route_region and (driver_territory in route_region or route_region in driver_territory):
        score += 20
        reasons.append("territory overlap")
    else:
        reasons.append("available active driver")
    if route.driver_id == driver.id:
        score += 10
        reasons.append("currently assigned")
    if active_route_count == 0:
        score += 15
        reasons.append("no active routes")
    else:
        score -= min(active_route_count * 8, 30)
        reasons.append(f"{active_route_count} active route(s)")
    return {
        "driver": driver,
        "score": max(score, 0),
        "reason": ", ".join(reasons),
        "active_route_count": active_route_count,
    }


def assign_route_to_driver(db: Session, route: Route, driver_id: int | None) -> None:
    route.driver_id = driver_id
    if driver_id and route.route_status == "planned":
        route.route_status = "assigned"
    ensure_route_payout(db, route)
