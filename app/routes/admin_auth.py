from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.services.auth import authenticate_admin


router = APIRouter(prefix="/admin", tags=["admin-auth"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    admin = authenticate_admin(db, email, password)
    if not admin:
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid admin credentials."}, status_code=401)
    request.session["admin_user_id"] = admin.id
    request.session["admin_email"] = admin.email
    return RedirectResponse("/admin/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
