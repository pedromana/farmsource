from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    ClassificationLog,
    Producer,
    RawScrapeRecord,
    ScrapeError,
    ScrapeRun,
    SourceProvider,
    ValidationLog,
)
from app.provider_config import ProviderConfig, load_provider_configs, sync_provider_configs
from scrapers.common.url_utils import normalize_url
from scrapers.common.validators import DestinationValidator
from scrapers.registry import provider_for

LOGGER = logging.getLogger(__name__)


def run_scrapers(session: Session, provider_name: str | None = None) -> list[ScrapeRun]:
    configs = load_provider_configs()
    sync_provider_configs(session, configs)
    selected = [config for config in configs if config.enabled and (provider_name is None or config.name == provider_name)]
    runs: list[ScrapeRun] = []
    for config in selected:
        runs.append(run_provider(session, config))
    return runs


def run_provider(session: Session, config: ProviderConfig) -> ScrapeRun:
    run = ScrapeRun(provider_name=config.name, status="running")
    session.add(run)
    session.commit()
    provider_row = session.query(SourceProvider).filter(SourceProvider.name == config.name).one_or_none()

    try:
        provider = provider_for(config)
        validator = DestinationValidator(config)
        listings = provider.scrape(run.resume_cursor)
        run.listings_seen = len(listings)
        for listing in listings:
            destination = listing.buy_online_url or listing.website_url
            fetch, classification = validator.validate(destination)
            producer = upsert_producer(session, listing, classification)
            run.producers_saved += 1
            if producer.online_ordering_confirmed:
                run.qualified_saved += 1
            session.add(
                RawScrapeRecord(
                    provider_name=config.name,
                    scrape_run_id=run.id,
                    producer_id=producer.id,
                    url=listing.source_listing_url,
                    raw_html=listing.raw_html,
                    raw_text=listing.raw_text,
                    metadata_json=json.dumps(listing.metadata or {}),
                )
            )
            session.add(
                ValidationLog(
                    provider_name=config.name,
                    producer_id=producer.id,
                    url=fetch.requested_url,
                    status_code=fetch.status_code,
                    final_url=fetch.final_url,
                    destination_type=classification.destination_type,
                    platform_detected=classification.platform_detected,
                    confidence_score=classification.confidence_score,
                    reason=fetch.error or classification.classification_reason,
                )
            )
            session.add(
                ClassificationLog(
                    producer_id=producer.id,
                    input_url=destination,
                    destination_type=classification.destination_type,
                    platform_detected=classification.platform_detected,
                    matched_indicators=", ".join(classification.matched_indicators),
                    reason=classification.classification_reason,
                )
            )
            session.commit()
        validator.close()
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        run.message = f"Saved {run.producers_saved} producers; {run.qualified_saved} qualified."
        if provider_row:
            provider_row.last_health_status = "ok"
            provider_row.last_error = None
    except Exception as exc:
        LOGGER.exception("Provider run failed for %s", config.name)
        run.status = "failed"
        run.finished_at = datetime.utcnow()
        run.message = str(exc)
        session.add(
            ScrapeError(
                provider_name=config.name,
                scrape_run_id=run.id,
                error_type=type(exc).__name__,
                message=str(exc),
                traceback=traceback.format_exc(),
            )
        )
        if provider_row:
            provider_row.last_health_status = "failed"
            provider_row.last_error = str(exc)
    session.commit()
    return run


def upsert_producer(session: Session, listing, classification) -> Producer:
    source_listing_url = normalize_url(listing.source_listing_url)
    buy_online_url = normalize_url(listing.buy_online_url)
    producer = (
        session.query(Producer)
        .filter(
            Producer.source_name == listing.source_name,
            Producer.source_listing_url == source_listing_url,
            Producer.buy_online_url == buy_online_url,
        )
        .one_or_none()
    )
    if producer is None:
        producer = Producer(source_name=listing.source_name, farm_name=listing.farm_name)
        session.add(producer)

    producer.source_region = listing.source_region
    producer.source_listing_id = listing.source_listing_id
    producer.source_category = listing.source_category
    producer.farm_name = listing.farm_name
    producer.listing_url = normalize_url(listing.listing_url)
    producer.source_listing_url = source_listing_url
    producer.buy_online_url = buy_online_url
    producer.website_url = normalize_url(listing.website_url)
    producer.city = listing.city
    producer.county = listing.county
    producer.state = listing.state
    producer.products = listing.products
    producer.destination_type = classification.destination_type
    producer.platform_detected = classification.platform_detected
    producer.online_ordering_confirmed = classification.online_ordering_confirmed
    producer.confidence_score = classification.confidence_score
    producer.classification_reason = classification.classification_reason
    producer.pickup_available = classification.pickup_available
    producer.delivery_available = classification.delivery_available
    producer.phone = listing.phone
    producer.email_or_contact_url = listing.email_or_contact_url
    producer.last_checked_date = datetime.utcnow()
    session.commit()
    session.refresh(producer)
    return producer
