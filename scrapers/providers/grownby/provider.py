from __future__ import annotations

from scrapers.base import BaseProvider, ProducerListing


class GrownByProvider(BaseProvider):
    def scrape(self, resume_cursor: str | None = None) -> list[ProducerListing]:
        return []

    def test_connection(self) -> tuple[bool, str]:
        return False, "Provider scaffold exists but scraping logic is not implemented yet."
