from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/customer", response_class=HTMLResponse)
def customer_app(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("customer.html", {"request": request})


@router.get("/driver", response_class=HTMLResponse)
def driver_app(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("driver.html", {"request": request})
