from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Producer(Base, TimestampMixin):
    __tablename__ = "producers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), index=True)
    producer_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    business_name: Mapped[str | None] = mapped_column(String(255), index=True)
    website_url: Mapped[str | None] = mapped_column(String(500), index=True)
    online_order_url: Mapped[str | None] = mapped_column(String(500), index=True)
    source_listing_url: Mapped[str | None] = mapped_column(String(500), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    county: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(40), index=True)
    zip_code: Mapped[str | None] = mapped_column(String(20))
    products: Mapped[str | None] = mapped_column(Text)
    producer_type: Mapped[str | None] = mapped_column(String(120))
    delivery_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pickup_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    online_ordering_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    destination_type: Mapped[str] = mapped_column(String(80), default="unknown", nullable=False)
    platform_detected: Mapped[str | None] = mapped_column(String(120))
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source | None] = relationship(back_populates="producers")
    catalog_products: Mapped[list["Product"]] = relationship(back_populates="producer")


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(120), index=True)
    source_url: Mapped[str | None] = mapped_column(String(500))
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    state: Mapped[str | None] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    producers: Mapped[list[Producer]] = relationship(back_populates="source")
    import_runs: Mapped[list["ImportRun"]] = relationship(back_populates="source")


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source: Mapped[Source | None] = relationship(back_populates="import_runs")
    error_rows: Mapped[list["ImportErrorRow"]] = relationship(
        back_populates="import_run",
        cascade="all, delete-orphan",
    )


class ImportErrorRow(Base):
    __tablename__ = "import_error_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_data: Mapped[str | None] = mapped_column(Text)

    import_run: Mapped[ImportRun] = relationship(back_populates="error_rows")


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class DeliveryWindow(Base, TimestampMixin):
    __tablename__ = "delivery_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    start_time: Mapped[str | None] = mapped_column(String(20))
    end_time: Mapped[str | None] = mapped_column(String(20))
    max_orders: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    current_order_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    availability: Mapped[list["ProductAvailability"]] = relationship(back_populates="delivery_window")
    orders: Mapped[list["Order"]] = relationship(back_populates="delivery_window")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    producer_id: Mapped[int | None] = mapped_column(ForeignKey("producers.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    short_description: Mapped[str | None] = mapped_column(String(500))
    full_description: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(80), default="each", nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    compare_at_price: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    seasonal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    delivery_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    producer: Mapped[Producer | None] = relationship(back_populates="catalog_products")
    category: Mapped[ProductCategory | None] = relationship(back_populates="products")
    availability: Mapped[list["ProductAvailability"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="product")


class ProductAvailability(Base, TimestampMixin):
    __tablename__ = "product_availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    delivery_window_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_windows.id"), index=True)
    available_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    available_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    product: Mapped[Product] = relationship(back_populates="availability")
    delivery_window: Mapped[DeliveryWindow | None] = relationship(back_populates="availability")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="images")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(80))
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    cart_sessions: Mapped[list["CartSession"]] = relationship(back_populates="customer")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    order_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    delivery_window_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_windows.id"), index=True)
    delivery_address: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_city: Mapped[str] = mapped_column(String(120), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(40), nullable=False)
    delivery_zip: Mapped[str] = mapped_column(String(20), nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    taxes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(40), default="unpaid", nullable=False, index=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    route_id: Mapped[int | None] = mapped_column(Integer, index=True)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    delivery_window: Mapped[DeliveryWindow | None] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class CartSession(Base, TimestampMixin):
    __tablename__ = "cart_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)

    customer: Mapped[Customer | None] = relationship(back_populates="cart_sessions")
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart_session", cascade="all, delete-orphan")


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_session_id: Mapped[int] = mapped_column(ForeignKey("cart_sessions.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cart_session: Mapped[CartSession] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="cart_items")


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(80), default="admin", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Driver(Base, TimestampMixin):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(80))
    territory: Mapped[str | None] = mapped_column(String(120), index=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    routes: Mapped[list["Route"]] = relationship(back_populates="driver")
    payouts: Mapped[list["DriverPayout"]] = relationship(back_populates="driver")


class Route(Base, TimestampMixin):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    delivery_window_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_windows.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    route_status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False, index=True)
    estimated_start_time: Mapped[str | None] = mapped_column(String(20))
    estimated_end_time: Mapped[str | None] = mapped_column(String(20))
    estimated_stop_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_order_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    route_pay: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    route_bonus: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reassignment_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    assignment_notes: Mapped[str | None] = mapped_column(Text)
    route_notes: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    delivery_window: Mapped[DeliveryWindow | None] = relationship()
    driver: Mapped[Driver | None] = relationship(back_populates="routes")
    stops: Mapped[list["RouteStop"]] = relationship(back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.stop_sequence")
    payout: Mapped["DriverPayout | None"] = relationship(back_populates="route", cascade="all, delete-orphan", uselist=False)


class RouteStop(Base, TimestampMixin):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    stop_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stop_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(40))
    zip_code: Mapped[str | None] = mapped_column(String(20))
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    driver_notes: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_reason: Mapped[str | None] = mapped_column(Text)
    proof_of_delivery_url: Mapped[str | None] = mapped_column(String(1000))

    route: Mapped[Route] = relationship(back_populates="stops")
    order: Mapped[Order] = relationship()


class DriverPayout(Base, TimestampMixin):
    __tablename__ = "driver_payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), index=True, unique=True)
    base_route_pay: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    bonus_pay: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tip_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_pay: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payout_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    payout_notes: Mapped[str | None] = mapped_column(Text)

    driver: Mapped[Driver | None] = relationship(back_populates="payouts")
    route: Mapped[Route | None] = relationship(back_populates="payout")
