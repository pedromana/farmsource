from __future__ import annotations

import logging
import re
import urllib.robotparser
from hashlib import sha1
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.provider_config import ProviderConfig
from scrapers.base import BaseProvider, ProducerListing
from scrapers.common.throttling import PoliteThrottle
from scrapers.common.url_utils import normalize_url
from scrapers.common.validators import USER_AGENT

LOGGER = logging.getLogger(__name__)


class WAFoodFarmFinderProvider(BaseProvider):
    """Scraper for Eat Local First's WA Food & Farm Finder public directory."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self.throttle = PoliteThrottle(config.crawl_delay_seconds, config.rate_limit_per_minute)
        self.client = httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            response = self.client.get(self.config.base_url)
            if response.status_code >= 400:
                return False, f"Source returned HTTP {response.status_code}."
            return True, f"Connected with HTTP {response.status_code}."
        except httpx.HTTPError as exc:
            return False, str(exc)

    def scrape(self, resume_cursor: str | None = None) -> list[ProducerListing]:
        if not self._can_fetch(self.config.base_url):
            LOGGER.warning("robots.txt disallows %s", self.config.base_url)
            return []
        html_by_url = self._crawl_pages(resume_cursor)
        listings: list[ProducerListing] = []
        for page_url, html in html_by_url.items():
            listings.extend(self._parse_page(page_url, html))
        return self._dedupe(listings)

    def _can_fetch(self, url: str) -> bool:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(urljoin(self.config.base_url, "/robots.txt"))
        try:
            parser.read()
        except Exception as exc:
            LOGGER.info("Could not read robots.txt: %s", exc)
        return parser.can_fetch(USER_AGENT, url) or parser.can_fetch("*", url)

    def _crawl_pages(self, resume_cursor: str | None = None) -> dict[str, str]:
        start_url = resume_cursor or self.config.base_url
        seen: set[str] = set()
        queue: list[str] = [start_url]
        pages: dict[str, str] = {}
        max_pages = self.config.max_pages or 1000

        while queue and len(pages) < max_pages:
            url = queue.pop(0)
            normalized = normalize_url(url, self.config.base_url)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            if not self._can_fetch(normalized):
                continue
            html = self._fetch_html(normalized)
            if not html:
                continue
            pages[normalized] = html
            for next_url in self._pagination_links(normalized, html):
                if next_url not in seen and len(pages) + len(queue) < max_pages:
                    queue.append(next_url)
        return pages

    def _fetch_html(self, url: str) -> str | None:
        self.throttle.wait()
        try:
            response = self.client.get(url)
            if response.status_code == 403:
                LOGGER.warning("HTTP 403 from %s. Not bypassing access controls.", url)
                return self._fetch_with_playwright(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            LOGGER.warning("HTTP fetch failed for %s: %s", url, exc)
            return self._fetch_with_playwright(url)

    def _fetch_with_playwright(self, url: str) -> str | None:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError:
            LOGGER.info("Playwright is not installed; skipping browser fallback.")
            return None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000)
                if response and response.status >= 400:
                    LOGGER.warning("Browser fetch returned HTTP %s for %s", response.status, url)
                    browser.close()
                    return None
                page.wait_for_timeout(2500)
                html = page.content()
                browser.close()
                return html
        except PlaywrightError as exc:
            LOGGER.warning("Playwright fetch failed for %s: %s", url, exc)
            return None

    def _pagination_links(self, page_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        selectors = self.config.pagination.get("next_selectors") or ["a[rel='next']", "a.next", ".pagination a"]
        links: list[str] = []
        for selector in selectors:
            for link in soup.select(selector):
                href = link.get("href")
                normalized = normalize_url(href, page_url)
                if normalized and normalized.startswith(normalize_url(self.config.base_url) or self.config.base_url):
                    links.append(normalized)
        return links

    def _parse_page(self, page_url: str, html: str) -> list[ProducerListing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = self._candidate_cards(soup)
        listings = [listing for card in cards if (listing := self._parse_card(page_url, card))]
        if listings:
            return listings
        return self._parse_buy_online_links(page_url, soup, html)

    def _candidate_cards(self, soup: BeautifulSoup) -> list[Tag]:
        selectors = [
            "[class*='listing']",
            "[class*='directory'] article",
            "[class*='farm']",
            ".card",
            "article",
        ]
        cards: list[Tag] = []
        for selector in selectors:
            for item in soup.select(selector):
                text = item.get_text(" ", strip=True).lower()
                if "buy online" in text or "website" in text or "farm" in text:
                    cards.append(item)
        return cards

    def _parse_card(self, page_url: str, card: Tag) -> ProducerListing | None:
        text = card.get_text(" ", strip=True)
        buy_link = self._link_matching(card, ["buy online", "order online", "shop", "store"])
        website_link = self._link_matching(card, ["website", "visit"])
        if not buy_link and not website_link:
            return None
        name_node = card.find(["h1", "h2", "h3", "h4"]) or card.find("a")
        farm_name = name_node.get_text(" ", strip=True) if name_node else self._derive_name(text)
        if not farm_name:
            return None
        listing_link = self._first_internal_link(page_url, card)
        city, county, state = self._parse_location(text)
        return ProducerListing(
            source_name=self.config.name,
            source_region=self.config.region,
            source_listing_id=self._listing_id(listing_link or page_url, farm_name),
            source_category=None,
            farm_name=farm_name,
            listing_url=listing_link or page_url,
            source_listing_url=listing_link or page_url,
            buy_online_url=normalize_url(buy_link, page_url),
            website_url=normalize_url(website_link, page_url),
            city=city,
            county=county,
            state=state or "WA",
            products=self._parse_products(text),
            raw_html=str(card),
            raw_text=text,
            metadata={"parser": "card"},
        )

    def _parse_buy_online_links(self, page_url: str, soup: BeautifulSoup, html: str) -> list[ProducerListing]:
        listings: list[ProducerListing] = []
        for link in soup.find_all("a"):
            label = link.get_text(" ", strip=True).lower()
            if not any(token in label for token in ["buy online", "order online", "shop", "store"]):
                continue
            farm_name = self._nearby_heading(link) or self._derive_name(link.parent.get_text(" ", strip=True) if link.parent else "")
            if not farm_name:
                farm_name = "Unknown producer"
            url = normalize_url(link.get("href"), page_url)
            listings.append(
                ProducerListing(
                    source_name=self.config.name,
                    source_region=self.config.region,
                    source_listing_id=self._listing_id(page_url, farm_name),
                    source_category=None,
                    farm_name=farm_name,
                    listing_url=page_url,
                    source_listing_url=page_url,
                    buy_online_url=url,
                    website_url=None,
                    state="WA",
                    raw_html=html[:5000],
                    raw_text=soup.get_text(" ", strip=True)[:5000],
                    metadata={"parser": "buy_online_link"},
                )
            )
        return listings

    def _link_matching(self, card: Tag, labels: list[str]) -> str | None:
        for link in card.find_all("a"):
            text = link.get_text(" ", strip=True).lower()
            href = link.get("href")
            if href and any(label in text or label in href.lower() for label in labels):
                return href
        return None

    def _first_internal_link(self, page_url: str, card: Tag) -> str | None:
        base = normalize_url(self.config.base_url) or self.config.base_url
        for link in card.find_all("a"):
            href = normalize_url(link.get("href"), page_url)
            if href and href.startswith(base):
                return href
        return None

    def _nearby_heading(self, node: Tag) -> str | None:
        current: Tag | None = node
        for _ in range(4):
            if current is None:
                return None
            heading = current.find_previous(["h1", "h2", "h3", "h4"])
            if heading:
                return heading.get_text(" ", strip=True)
            current = current.parent if isinstance(current.parent, Tag) else None
        return None

    def _derive_name(self, text: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            return None
        return cleaned.split(" Buy Online ")[0].split(" Website ")[0][:300].strip()

    def _parse_location(self, text: str) -> tuple[str | None, str | None, str | None]:
        match = re.search(r"\b([A-Z][A-Za-z .'-]+),\s*(WA|Washington)\b", text)
        if match:
            return match.group(1).strip(), None, "WA"
        county_match = re.search(r"\b([A-Z][A-Za-z .'-]+)\s+County\b", text)
        return None, county_match.group(1).strip() if county_match else None, "WA"

    def _parse_products(self, text: str) -> str | None:
        labels = ["Products:", "Product Categories:", "Categories:"]
        for label in labels:
            if label in text:
                return text.split(label, 1)[1].split(" Website", 1)[0].split(" Buy Online", 1)[0].strip()
        return None

    def _listing_id(self, url: str | None, farm_name: str) -> str:
        basis = f"{url or ''}|{farm_name}".encode("utf-8")
        return sha1(basis).hexdigest()[:16]

    def _dedupe(self, listings: list[ProducerListing]) -> list[ProducerListing]:
        seen: set[tuple[str, str | None]] = set()
        unique: list[ProducerListing] = []
        for listing in listings:
            key = (listing.farm_name.lower(), listing.buy_online_url or listing.website_url)
            if key in seen:
                continue
            seen.add(key)
            unique.append(listing)
        return unique
