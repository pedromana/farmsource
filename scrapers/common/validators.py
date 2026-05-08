from __future__ import annotations

import logging
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.provider_config import ProviderConfig
from scrapers.common.classifiers import ClassificationResult, classify_destination
from scrapers.common.throttling import PoliteThrottle
from scrapers.common.url_utils import normalize_url

LOGGER = logging.getLogger(__name__)
USER_AGENT = "FarmSourceBot/0.1 (+local research; respects robots.txt)"


@dataclass(slots=True)
class ValidationFetch:
    requested_url: str
    final_url: str | None
    status_code: int | None
    html: str | None
    error: str | None = None


class DestinationValidator:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.throttle = PoliteThrottle(config.crawl_delay_seconds, config.rate_limit_per_minute)
        self.client = httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def close(self) -> None:
        self.client.close()

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
        parser = self._robots_cache.get(robots_url)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
            except Exception as exc:
                LOGGER.info("Could not read robots.txt for %s: %s", robots_url, exc)
            self._robots_cache[robots_url] = parser
        return parser.can_fetch(USER_AGENT, url) or parser.can_fetch("*", url)

    def fetch(self, url: str) -> ValidationFetch:
        normalized = normalize_url(url)
        if not normalized:
            return ValidationFetch(url, None, None, None, "Invalid URL.")
        if not self.can_fetch(normalized):
            return ValidationFetch(normalized, None, 403, None, "robots.txt disallows fetching this URL.")
        last_error: str | None = None
        for _ in range(max(self.config.max_retries, 1)):
            self.throttle.wait()
            try:
                response = self.client.get(normalized)
                content_type = response.headers.get("content-type", "")
                html = response.text if "text/html" in content_type or "text/" in content_type else ""
                return ValidationFetch(normalized, str(response.url), response.status_code, html)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                LOGGER.warning("Validation fetch failed for %s: %s", normalized, exc)
        return ValidationFetch(normalized, None, None, None, last_error)

    def validate(self, url: str | None) -> tuple[ValidationFetch, ClassificationResult]:
        if not url:
            fetch = ValidationFetch("", None, None, None, "No URL")
            return fetch, classify_destination(None, None, None, self.config.blocked_domains)
        fetch = self.fetch(url)
        classify_url = fetch.final_url or fetch.requested_url
        result = classify_destination(classify_url, fetch.html, fetch.status_code, self.config.blocked_domains)
        return fetch, result
