from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.database import check_database


router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    settings = get_settings()
    try:
        check_database()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
