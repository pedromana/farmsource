from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceBase(BaseModel):
    source_name: str
    source_type: str | None = None
    source_url: str | None = None
    region: str | None = None
    state: str | None = None
    enabled: bool = True
    notes: str | None = None


class SourceRead(SourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProducerBase(BaseModel):
    source_id: int | None = None
    producer_name: str
    business_name: str | None = None
    website_url: str | None = None
    online_order_url: str | None = None
    source_listing_url: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    products: str | None = None
    producer_type: str | None = None
    delivery_available: bool = False
    pickup_available: bool = False
    online_ordering_confirmed: bool = False
    qualified: bool = False
    destination_type: str = "unknown"
    platform_detected: str | None = None
    confidence_score: float = 0.0
    classification_reason: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ProducerRead(ProducerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportRunRead(BaseModel):
    id: int
    source_id: int | None = None
    filename: str
    total_rows: int
    imported_rows: int
    skipped_rows: int
    error_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
