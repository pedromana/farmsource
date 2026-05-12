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


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(80), default="item", nullable=False)
