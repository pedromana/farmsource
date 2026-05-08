from __future__ import annotations

from dataclasses import dataclass

from app.provider_config import ProviderConfig


@dataclass(slots=True)
class ProducerListing:
    source_name: str
    source_region: str | None
    source_listing_id: str | None
    source_category: str | None
    farm_name: str
    listing_url: str | None
    source_listing_url: str | None
    buy_online_url: str | None
    website_url: str | None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    products: str | None = None
    phone: str | None = None
    email_or_contact_url: str | None = None
    raw_html: str | None = None
    raw_text: str | None = None
    metadata: dict | None = None


class BaseProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def scrape(self, resume_cursor: str | None = None) -> list[ProducerListing]:
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError
