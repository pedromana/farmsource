import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, get_settings
from app.database import init_db
from app.database import SessionLocal
from app.routes import admin, admin_auth, customer, health, pages, payments
from app.services.logging import configure_logging
from app.services.seed import seed_sample_catalog


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    with SessionLocal() as db:
        seed_sample_catalog(db)
    logger.info("Farmsource started", extra={"app_env": settings.app_env})
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    same_site="lax",
    https_only=False,
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "app" / "static"),
    name="static",
)

app.include_router(health.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)
app.include_router(customer.router)
app.include_router(payments.router)
app.include_router(pages.router)
