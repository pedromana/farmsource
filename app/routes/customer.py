from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import BASE_DIR
from app.database import get_db
from app.models import Product, ProductCategory
from app.services.catalog import (
    active_delivery_window,
    active_product_query,
    current_availability_for_product,
    featured_products,
    remaining_inventory,
)


router = APIRouter(prefix="/customer", tags=["customer"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/catalog", response_class=HTMLResponse)
def catalog(request: Request, db: Annotated[Session, Depends(get_db)]):
    window = active_delivery_window(db)
    window_id = window.id if window else None
    products = db.scalars(active_product_query(window_id).order_by(Product.featured.desc(), Product.name)).all()
    categories = db.scalars(
        select(ProductCategory).where(ProductCategory.active.is_(True)).order_by(ProductCategory.name)
    ).all()
    return templates.TemplateResponse(
        "customer_catalog.html",
        {
            "request": request,
            "products": products,
            "featured_products": featured_products(db),
            "categories": categories,
            "delivery_window": window,
            "remaining_inventory": remaining_inventory,
            "current_availability_for_product": current_availability_for_product,
            "placeholder_image": _placeholder_image(),
        },
    )


@router.get("/category/{category_id}", response_class=HTMLResponse)
def category_catalog(category_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    category = db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    window = active_delivery_window(db)
    window_id = window.id if window else None
    products = db.scalars(
        active_product_query(window_id)
        .where(Product.category_id == category_id)
        .order_by(Product.name)
    ).all()
    categories = db.scalars(
        select(ProductCategory).where(ProductCategory.active.is_(True)).order_by(ProductCategory.name)
    ).all()
    return templates.TemplateResponse(
        "customer_category.html",
        {
            "request": request,
            "category": category,
            "products": products,
            "categories": categories,
            "delivery_window": window,
            "remaining_inventory": remaining_inventory,
            "current_availability_for_product": current_availability_for_product,
            "placeholder_image": _placeholder_image(),
        },
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    product = db.scalars(
        select(Product)
        .options(
            selectinload(Product.producer),
            selectinload(Product.category),
            selectinload(Product.availability),
            selectinload(Product.images),
        )
        .where(Product.id == product_id)
    ).first()
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Product not found")
    window = active_delivery_window(db)
    availability = current_availability_for_product(product, window)
    return templates.TemplateResponse(
        "customer_product.html",
        {
            "request": request,
            "product": product,
            "delivery_window": window,
            "availability": availability,
            "remaining_inventory": remaining_inventory,
            "placeholder_image": _placeholder_image(),
        },
    )


def _placeholder_image() -> str:
    return "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80"
