import hashlib
import hmac
import os

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdminUser, Driver


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, digest)


def authenticate_admin(db: Session, email: str, password: str) -> AdminUser | None:
    admin = db.scalars(select(AdminUser).where(AdminUser.email == email.strip().lower(), AdminUser.active.is_(True))).first()
    if not admin or not verify_password(password, admin.password_hash):
        return None
    return admin


def authenticate_driver(db: Session, email: str, password: str) -> Driver | None:
    driver = db.scalars(select(Driver).where(Driver.email == email.strip().lower(), Driver.active.is_(True))).first()
    if not driver or not driver.password_hash or not verify_password(password, driver.password_hash):
        return None
    return driver


def require_admin(request: Request) -> int:
    admin_id = request.session.get("admin_user_id")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
            detail="Admin login required",
        )
    return int(admin_id)
