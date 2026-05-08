from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SourceProvider(TimestampMixin, Base):
    __tablename__ = "source_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    base_url: Mapped[str] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    source_type: Mapped[str | None] = mapped_column(String(120))
    refresh_interval_hours: Mapped[int | None] = mapped_column(Integer)
    crawl_delay_seconds: Mapped[float] = mapped_column(Float, default=2)
    max_pages: Mapped[int | None] = mapped_column(Integer)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=25)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)
    config_json: Mapped[str | None] = mapped_column(Text)
    last_health_status: Mapped[str | None] = mapped_column(String(60))
    last_error: Mapped[str | None] = mapped_column(Text)


class ScrapeRun(TimestampMixin, Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    listings_seen: Mapped[int] = mapped_column(Integer, default=0)
    producers_saved: Mapped[int] = mapped_column(Integer, default=0)
    qualified_saved: Mapped[int] = mapped_column(Integer, default=0)
    resume_cursor: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)


class Producer(TimestampMixin, Base):
    __tablename__ = "producers"
    __table_args__ = (
        UniqueConstraint("source_name", "source_listing_url", "buy_online_url", name="uq_source_listing_buy_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_region: Mapped[str | None] = mapped_column(String(120), index=True)
    source_listing_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source_category: Mapped[str | None] = mapped_column(String(200), index=True)
    farm_name: Mapped[str] = mapped_column(String(300), index=True)
    listing_url: Mapped[str | None] = mapped_column(Text)
    source_listing_url: Mapped[str | None] = mapped_column(Text)
    buy_online_url: Mapped[str | None] = mapped_column(Text, index=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(160), index=True)
    county: Mapped[str | None] = mapped_column(String(160), index=True)
    state: Mapped[str | None] = mapped_column(String(80), index=True)
    products: Mapped[str | None] = mapped_column(Text)
    destination_type: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    platform_detected: Mapped[str | None] = mapped_column(String(160), index=True)
    online_ordering_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    pickup_available: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    delivery_available: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(80))
    email_or_contact_url: Mapped[str | None] = mapped_column(Text)
    last_checked_date: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    raw_records: Mapped[list["RawScrapeRecord"]] = relationship(back_populates="producer")


class RawScrapeRecord(TimestampMixin, Base):
    __tablename__ = "raw_scrape_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), index=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"))
    producer_id: Mapped[int | None] = mapped_column(ForeignKey("producers.id"))
    url: Mapped[str | None] = mapped_column(Text)
    raw_html: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)

    producer: Mapped[Producer | None] = relationship(back_populates="raw_records")


class ScrapeError(TimestampMixin, Base):
    __tablename__ = "scrape_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), index=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"))
    url: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)


class ValidationLog(TimestampMixin, Base):
    __tablename__ = "validation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), index=True)
    producer_id: Mapped[int | None] = mapped_column(ForeignKey("producers.id"))
    url: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    final_url: Mapped[str | None] = mapped_column(Text)
    destination_type: Mapped[str] = mapped_column(String(80))
    platform_detected: Mapped[str | None] = mapped_column(String(160))
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(Text)


class ClassificationLog(TimestampMixin, Base):
    __tablename__ = "classification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producer_id: Mapped[int | None] = mapped_column(ForeignKey("producers.id"))
    input_url: Mapped[str | None] = mapped_column(Text)
    destination_type: Mapped[str] = mapped_column(String(80))
    platform_detected: Mapped[str | None] = mapped_column(String(160))
    matched_indicators: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
