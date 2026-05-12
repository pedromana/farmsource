from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdminUser, CartItem, CartSession, Customer, DeliveryWindow, Driver, DriverInterest, DriverPayout, Order, OrderItem, Producer, ProducerInterest, Product, ProductAvailability, ProductCategory, Route, RouteStop, Source, WaitlistSignup
from app.services.auth import hash_password
from app.services.delivery import ensure_route_payout, refresh_route_estimates, sync_stop_from_order


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
    _ensure_admin_user(db)
    if db.scalar(select(Product.id).limit(1)):
        _ensure_window_fields(db)
        _ensure_sample_public_leads(db)
        _ensure_sample_customer_order(db)
        _ensure_sample_operations(db)
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
            start_time="4:00 PM",
            end_time="7:00 PM",
            max_orders=40,
            current_order_count=0,
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
    _ensure_sample_public_leads(db)
    _ensure_sample_customer_order(db)
    _ensure_sample_operations(db)


def _ensure_admin_user(db: Session) -> None:
    settings = get_settings()
    email = settings.admin_default_email.strip().lower()
    if db.scalars(select(AdminUser).where(AdminUser.email == email)).first():
        return
    db.add(
        AdminUser(
            email=email,
            password_hash=hash_password(settings.admin_default_password),
            first_name="Farmsource",
            last_name="Admin",
            role="admin",
            active=True,
        )
    )
    db.commit()


def _ensure_window_fields(db: Session) -> None:
    for window in db.scalars(select(DeliveryWindow)).all():
        if not window.start_time:
            window.start_time = "4:00 PM"
        if not window.end_time:
            window.end_time = "7:00 PM"
        if not window.max_orders:
            window.max_orders = 40
    db.commit()


def _ensure_sample_customer_order(db: Session) -> None:
    if db.scalar(select(Order.id).limit(1)):
        return
    product = db.scalars(select(Product).where(Product.active.is_(True))).first()
    window = db.scalars(select(DeliveryWindow).where(DeliveryWindow.active.is_(True))).first()
    if not product or not window:
        return
    customer = Customer(
        first_name="Sample",
        last_name="Customer",
        email="sample.customer@example.com",
        phone="206-555-0100",
        address_line_1="123 Pike St",
        city="Seattle",
        state="WA",
        zip_code="98101",
        delivery_notes="Leave by the front door.",
        active=True,
    )
    db.add(customer)
    db.flush()
    cart = CartSession(session_id="sample-cart-session", customer_id=customer.id, status="converted")
    db.add(cart)
    db.flush()
    db.add(CartItem(cart_session_id=cart.id, product_id=product.id, quantity=1))
    order = Order(
        customer_id=customer.id,
        order_number="FS-SAMPLE-0001",
        order_status="confirmed",
        delivery_window_id=window.id,
        delivery_address=customer.address_line_1,
        delivery_city=customer.city,
        delivery_state=customer.state,
        delivery_zip=customer.zip_code,
        subtotal=product.price,
        delivery_fee=6.99,
        taxes=0.0,
        total=round(product.price + 6.99, 2),
        payment_status="paid",
        paid_at=datetime.now(UTC),
        customer_notes="Sample order for local review.",
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price=product.price, total_price=product.price))
    availability = db.scalars(
        select(ProductAvailability).where(
            ProductAvailability.product_id == product.id,
            ProductAvailability.delivery_window_id == window.id,
        )
    ).first()
    if availability:
        availability.reserved_quantity += 1
    window.current_order_count += 1
    db.commit()


def _ensure_sample_public_leads(db: Session) -> None:
    if not db.scalars(select(WaitlistSignup).where(WaitlistSignup.email == "pilot.customer@example.com")).first():
        db.add(
            WaitlistSignup(
                signup_type="customer",
                first_name="Pilot",
                last_name="Customer",
                email="pilot.customer@example.com",
                city="Seattle",
                state="WA",
                zip_code="98103",
                notes="Interested in weekly produce boxes.",
                source_page="/waitlist",
            )
        )
    if not db.scalars(select(ProducerInterest).where(ProducerInterest.email == "grower@example.com")).first():
        db.add(
            ProducerInterest(
                business_name="Sample Valley Farm",
                contact_name="Sample Grower",
                email="grower@example.com",
                city="Seattle",
                state="WA",
                products="greens, carrots, herbs",
                delivery_capability="Can aggregate weekly orders for pickup.",
                online_ordering="No",
                notes="Sample producer lead.",
            )
        )
    if not db.scalars(select(DriverInterest).where(DriverInterest.email == "route.driver.lead@example.com")).first():
        db.add(
            DriverInterest(
                first_name="Route",
                last_name="Driver",
                email="route.driver.lead@example.com",
                city="Seattle",
                state="WA",
                vehicle_type="SUV",
                availability_notes="Weekday evenings.",
                territory_preference="North Seattle",
                notes="Sample driver lead.",
            )
        )
    db.commit()


def _ensure_sample_operations(db: Session) -> None:
    driver = db.scalars(select(Driver).where(Driver.email == "driver@example.com")).first()
    if not driver:
        driver = Driver(
            first_name="Sample",
            last_name="Driver",
            email="driver@example.com",
            password_hash=hash_password("Driver123!"),
            phone="206-555-0198",
            territory="Seattle",
            vehicle_type="Cargo van",
            active=True,
            notes="Sample driver for operations dashboard.",
        )
        db.add(driver)
        db.flush()
    elif not driver.password_hash:
        driver.password_hash = hash_password("Driver123!")

    window = db.scalars(select(DeliveryWindow).where(DeliveryWindow.active.is_(True))).first()
    route = db.scalars(select(Route).where(Route.route_name == "Seattle Pilot Route")).first()
    if not route:
        route = Route(
            route_name="Seattle Pilot Route",
            delivery_window_id=window.id if window else None,
            driver_id=driver.id,
            region="Seattle",
            route_status="planned",
            estimated_start_time="4:00 PM",
            estimated_end_time="7:00 PM",
            estimated_stop_count=0,
            estimated_order_count=0,
            route_pay=80.0,
            route_bonus=0.0,
            route_notes="Sample route for launch operations.",
            notes="Sample route for launch operations.",
        )
        db.add(route)
        db.flush()

    orders = db.scalars(select(Order).order_by(Order.created_at.asc()).limit(8)).all()
    existing_order_ids = {stop.order_id for stop in route.stops}
    next_sequence = len(route.stops) + 1
    for order in orders:
        if order.id in existing_order_ids:
            continue
        order.route_id = route.id
        db.add(
            stop := RouteStop(
                route_id=route.id,
                order_id=order.id,
                stop_sequence=next_sequence,
                stop_status="pending",
                delivery_notes=order.customer.delivery_notes if order.customer else None,
            )
        )
        db.flush()
        sync_stop_from_order(stop)
        next_sequence += 1
    for stop in route.stops:
        sync_stop_from_order(stop)
    refresh_route_estimates(route)
    payout = db.scalars(select(DriverPayout).where(DriverPayout.route_id == route.id)).first()
    if not payout:
        ensure_route_payout(db, route)
    db.commit()
