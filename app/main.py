from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.database import PROJECT_ROOT, SessionLocal, get_session, init_db
from app.exporter import export_producers, producer_query
from app.models import Producer, ScrapeError, ScrapeRun, SourceProvider
from app.provider_config import ProviderConfig, load_provider_configs, sync_provider_configs
from scrapers.registry import provider_for
from scrapers.runner import run_provider, run_scrapers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="FarmSource", version="0.1.0")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "app" / "static")), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as session:
        sync_provider_configs(session)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    providers = session.query(SourceProvider).order_by(SourceProvider.name).all()
    runs = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(20).all()
    errors = session.query(ScrapeError).order_by(ScrapeError.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "providers": providers, "runs": runs, "errors": errors},
    )


@app.get("/api/producers")
def api_producers(
    search: str | None = None,
    city: str | None = None,
    county: str | None = None,
    state: str | None = None,
    products: str | None = None,
    platform: str | None = None,
    destination_type: str | None = None,
    source: str | None = None,
    delivery: str | None = None,
    pickup: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    filters = locals().copy()
    filters.pop("session")
    filters.pop("page")
    filters.pop("per_page")
    query = producer_query(session, filters, qualified_only=True)
    total = query.count()
    rows = (
        query.order_by(Producer.confidence_score.desc(), Producer.farm_name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": row.id,
                "farm_name": row.farm_name,
                "city": row.city,
                "county": row.county,
                "state": row.state,
                "products": row.products,
                "source_name": row.source_name,
                "source_listing_url": row.source_listing_url,
                "buy_online_url": row.buy_online_url,
                "website_url": row.website_url,
                "destination_type": row.destination_type,
                "platform_detected": row.platform_detected,
                "confidence_score": row.confidence_score,
                "classification_reason": row.classification_reason,
                "pickup_available": row.pickup_available,
                "delivery_available": row.delivery_available,
                "last_checked_date": row.last_checked_date.isoformat() if row.last_checked_date else None,
            }
            for row in rows
        ],
    }


@app.get("/export")
def export_endpoint(
    search: str | None = None,
    city: str | None = None,
    county: str | None = None,
    state: str | None = None,
    products: str | None = None,
    platform: str | None = None,
    destination_type: str | None = None,
    source: str | None = None,
    delivery: str | None = None,
    pickup: str | None = None,
    session: Session = Depends(get_session),
) -> FileResponse:
    filters = locals().copy()
    filters.pop("session")
    path = export_producers(session, filters)
    return FileResponse(path, filename=Path(path).name)


@app.post("/admin/providers/sync")
def sync_providers(session: Session = Depends(get_session)) -> RedirectResponse:
    sync_provider_configs(session, load_provider_configs())
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/providers/{provider_name}/toggle")
def toggle_provider(provider_name: str, session: Session = Depends(get_session)) -> RedirectResponse:
    provider = session.query(SourceProvider).filter(SourceProvider.name == provider_name).one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.enabled = not provider.enabled
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/providers/{provider_name}/update")
def update_provider(
    provider_name: str,
    base_url: str = Form(...),
    crawl_delay_seconds: float = Form(...),
    max_pages: int = Form(...),
    rate_limit_per_minute: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    provider = session.query(SourceProvider).filter(SourceProvider.name == provider_name).one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.base_url = base_url
    provider.crawl_delay_seconds = crawl_delay_seconds
    provider.max_pages = max_pages
    provider.rate_limit_per_minute = rate_limit_per_minute
    config = json.loads(provider.config_json or "{}")
    config.update(
        {
            "base_url": base_url,
            "crawl_delay_seconds": crawl_delay_seconds,
            "max_pages": max_pages,
            "rate_limit_per_minute": rate_limit_per_minute,
        }
    )
    provider.config_json = json.dumps(config, indent=2, sort_keys=True)
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/providers/{provider_name}/test")
def test_provider(provider_name: str, session: Session = Depends(get_session)) -> RedirectResponse:
    provider = session.query(SourceProvider).filter(SourceProvider.name == provider_name).one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    config = ProviderConfig.from_dict(json.loads(provider.config_json or "{}"))
    ok, message = provider_for(config).test_connection()
    provider.last_health_status = "ok" if ok else "failed"
    provider.last_error = None if ok else message
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/providers/{provider_name}/rescan")
def rescan_provider(provider_name: str, session: Session = Depends(get_session)) -> RedirectResponse:
    configs = {config.name: config for config in load_provider_configs()}
    provider = session.query(SourceProvider).filter(SourceProvider.name == provider_name).one_or_none()
    if provider and provider.config_json:
        configs[provider_name] = ProviderConfig.from_dict(json.loads(provider.config_json))
    config = configs.get(provider_name)
    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")
    run_provider(session, config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/rescan")
def rescan_all(session: Session = Depends(get_session)) -> RedirectResponse:
    run_scrapers(session)
    return RedirectResponse("/admin", status_code=303)
