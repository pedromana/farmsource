from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import Driver, Route, RouteStop
from app.services.auth import authenticate_driver
from app.services.delivery import assigned_driver_routes, decline_route_by_driver, order_summary, route_progress, update_stop_status


router = APIRouter(prefix="/driver", tags=["driver"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def _current_driver(request: Request, db: Session) -> Driver | None:
    driver_id = request.session.get("driver_id")
    if not driver_id:
        return None
    return db.get(Driver, driver_id)


def _require_driver(request: Request, db: Session) -> Driver:
    driver = _current_driver(request, db)
    if not driver:
        raise HTTPException(status_code=303, headers={"Location": "/driver/login"})
    return driver


@router.get("", response_class=HTMLResponse)
def driver_home(request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _current_driver(request, db)
    if not driver:
        return RedirectResponse("/driver/login", status_code=303)
    return RedirectResponse("/driver/routes", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def driver_login_page(request: Request):
    return templates.TemplateResponse("driver_login.html", {"request": request, "error": None})


@router.post("/login")
async def driver_login(request: Request, db: Annotated[Session, Depends(get_db)]):
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")
    driver = authenticate_driver(db, email, password)
    if not driver:
        return templates.TemplateResponse("driver_login.html", {"request": request, "error": "Invalid driver email or password."}, status_code=400)
    request.session["driver_id"] = driver.id
    request.session["driver_email"] = driver.email
    return RedirectResponse("/driver/routes", status_code=303)


@router.get("/logout")
def driver_logout(request: Request):
    request.session.pop("driver_id", None)
    request.session.pop("driver_email", None)
    return RedirectResponse("/driver/login", status_code=303)


@router.get("/routes", response_class=HTMLResponse)
def driver_routes(request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _require_driver(request, db)
    routes = assigned_driver_routes(db, driver.id)
    return templates.TemplateResponse("driver_routes.html", {"request": request, "driver": driver, "routes": routes, "route_progress": route_progress})


@router.get("/route/{route_id}", response_class=HTMLResponse)
def driver_route_detail(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _require_driver(request, db)
    route = db.get(Route, route_id)
    if not route or route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Route not found")
    return templates.TemplateResponse(
        "driver_route_detail.html",
        {"request": request, "driver": driver, "route": route, "progress": route_progress(route), "order_summary": order_summary},
    )


@router.get("/stop/{stop_id}", response_class=HTMLResponse)
def driver_stop_detail(stop_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _require_driver(request, db)
    stop = db.get(RouteStop, stop_id)
    if not stop or not stop.route or stop.route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Stop not found")
    return templates.TemplateResponse(
        "driver_stop_detail.html",
        {"request": request, "driver": driver, "stop": stop, "order_summary": order_summary},
    )


@router.post("/stop/{stop_id}")
async def update_driver_stop(stop_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _require_driver(request, db)
    stop = db.get(RouteStop, stop_id)
    if not stop or not stop.route or stop.route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Stop not found")
    form = await request.form()
    try:
        update_stop_status(
            db,
            stop,
            str(form.get("action_status") or form.get("stop_status") or stop.stop_status),
            driver_notes=_optional(form.get("driver_notes")),
            failed_reason=_optional(form.get("failed_reason")),
            proof_of_delivery_url=_optional(form.get("proof_of_delivery_url")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/driver/route/{stop.route_id}", status_code=303)


@router.post("/route/{route_id}/decline")
async def decline_driver_route(route_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    driver = _require_driver(request, db)
    route = db.get(Route, route_id)
    if not route or route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Route not found")
    form = await request.form()
    decline_route_by_driver(db, route, driver, _optional(form.get("decline_reason")))
    return RedirectResponse("/driver/routes", status_code=303)


def _optional(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None
