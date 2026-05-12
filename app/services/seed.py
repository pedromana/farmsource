from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeliveryWindow, Producer, Product, ProductAvailability, ProductCategory, Source


CATEGORY_NAMES = [
    "Produce Boxes",
    "Vegetables",
    "Fruits",
    "Seasonal Bundles",
    "Herbs",
    "Add-ons",
    "Dairy",
    "Eggs",
    "Bakery",
    "Pantry",
]


def seed_sample_catalog(db: Session) -> None:
    if db.scalar(select(Product.id).limit(1)):
        return

    source = db.scalars(select(Source).where(Source.source_name == "Farmsource Sample Data")).first()
    if not source:
        source = Source(
            source_name="Farmsource Sample Data",
            source_type="sample",
            region="Seattle",
            state="WA",
            enabled=True,
            notes="Local v1 seed data for catalog development.",
        )
        db.add(source)
        db.flush()

    producer = db.scalars(select(Producer).where(Producer.producer_name == "Cedar Grove Farm")).first()
    if not producer:
        producer = Producer(
            source_id=source.id,
            producer_name="Cedar Grove Farm",
            business_name="Cedar Grove Farm",
            website_url="https://example.com/cedar-grove-farm",
            city="Seattle",
            county="King",
            state="WA",
            products="vegetables, herbs, seasonal produce boxes",
            producer_type="farm",
            delivery_available=True,
            pickup_available=True,
            online_ordering_confirmed=True,
            qualified=True,
            destination_type="ecommerce_store",
            confidence_score=0.7,
            classification_reason="Sample qualified producer.",
        )
        db.add(producer)
        db.flush()

    categories = {}
    for name in CATEGORY_NAMES:
        category = db.scalars(select(ProductCategory).where(ProductCategory.name == name)).first()
        if not category:
            category = ProductCategory(name=name, description=f"{name} for curated weekly offerings.", active=True)
            db.add(category)
            db.flush()
        categories[name] = category

    window = db.scalars(select(DeliveryWindow).where(DeliveryWindow.name == "Seattle Weekly Delivery")).first()
    if not window:
        window = DeliveryWindow(
            name="Seattle Weekly Delivery",
            region="Seattle",
            delivery_date=datetime.now(UTC) + timedelta(days=3),
            active=True,
            notes="Sample active delivery window.",
        )
        db.add(window)
        db.flush()

    products = [
        {
            "name": "Weekly Produce Box",
            "category": "Produce Boxes",
            "sku": "BOX-WEEKLY-PRODUCE",
            "unit": "box",
            "price": 34.0,
            "featured": True,
            "seasonal": True,
            "quantity": 24,
            "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80",
            "short_description": "A curated box of seasonal vegetables and fruit for the week.",
        },
        {
            "name": "Seasonal Vegetable Bundle",
            "category": "Seasonal Bundles",
            "sku": "BUNDLE-SEASONAL-VEG",
            "unit": "bundle",
            "price": 18.0,
            "featured": True,
            "seasonal": True,
            "quantity": 18,
            "image_url": "https://images.unsplash.com/photo-1566385101042-1a0aa0c1268c?auto=format&fit=crop&w=900&q=80",
            "short_description": "A rotating bundle of harvest-ready vegetables.",
        },
        {
            "name": "Fresh Herb Add-on",
            "category": "Herbs",
            "sku": "ADDON-FRESH-HERBS",
            "unit": "bunch",
            "price": 5.0,
            "featured": False,
            "seasonal": False,
            "quantity": 12,
            "image_url": "https://images.unsplash.com/photo-1515586000433-45406d8e6662?auto=format&fit=crop&w=900&q=80",
            "short_description": "A fresh herb bunch selected from current farm availability.",
        },
    ]

    now = datetime.now(UTC)
    for item in products:
        product = db.scalars(select(Product).where(Product.sku == item["sku"])).first()
        if product:
            continue
        product = Product(
            producer_id=producer.id,
            category_id=categories[item["category"]].id,
            name=item["name"],
            short_description=item["short_description"],
            full_description=item["short_description"],
            sku=item["sku"],
            unit=item["unit"],
            price=item["price"],
            image_url=item["image_url"],
            featured=item["featured"],
            active=True,
            seasonal=item["seasonal"],
            delivery_eligible=True,
        )
        db.add(product)
        db.flush()
        db.add(
            ProductAvailability(
                product_id=product.id,
                delivery_window_id=window.id,
                available_quantity=item["quantity"],
                reserved_quantity=0,
                status="active",
                available_from=now - timedelta(days=1),
                available_until=now + timedelta(days=10),
            )
        )

    db.commit()
