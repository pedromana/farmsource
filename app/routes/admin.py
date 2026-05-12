from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import ImportRun, Producer, Source
from app.services.classification import classify_producer_destination
from app.services.csv_importer import import_producers_from_csv
from app.services.exporter import producers_to_excel


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("")
def admin_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "source_count": db.scalar(select(func.count(Source.id))),
            "producer_count": db.scalar(select(func.count(Producer.id))),
            "qualified_count": db.scalar(select(func.count(Producer.id)).where(Producer.qualified.is_(True))),
        },
    )


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


def _optional(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _optional_int(value) -> int | None:
    value = _optional(value)
    return int(value) if value else None
