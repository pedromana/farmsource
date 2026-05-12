from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import (
    DeliveryWindow,
    ImportRun,
    Producer,
    Product,
    ProductAvailability,
    ProductCategory,
    ProductImage,
    Source,
)
from app.services.catalog import LOW_INVENTORY_THRESHOLD, low_inventory_availability
from app.services.classification import classify_producer_destination
from app.services.csv_importer import import_producers_from_csv
from app.services.exporter import availability_to_excel, producers_to_excel, products_to_excel


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
            "product_count": db.scalar(select(func.count(Product.id))),
        },
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


def _int(value, default: int) -> int:
    value = _optional(value)
    return int(value) if value else default


def _float(value, default: float) -> float:
    value = _optional(value)
    return float(value) if value else default


def _optional_float(value) -> float | None:
    value = _optional(value)
    return float(value) if value else None
