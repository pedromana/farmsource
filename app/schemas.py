from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProducerBase(BaseModel):
    name: str
    region: str = "Seattle"
    contact_email: str | None = None
    notes: str | None = None


class ProducerRead(ProducerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    category: str | None = None
    unit: str = "item"


class ProductRead(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
