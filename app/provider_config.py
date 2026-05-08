from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.models import SourceProvider

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER_CONFIG = PROJECT_ROOT / "config" / "providers.yaml"


@dataclass(slots=True)
class ProviderConfig:
    name: str
    enabled: bool
    base_url: str
    display_name: str | None = None
    region: str | None = None
    source_type: str | None = None
    refresh_interval_hours: int | None = None
    crawl_delay_seconds: float = 2
    max_pages: int | None = None
    max_retries: int = 3
    timeout_seconds: int = 25
    rate_limit_per_minute: int | None = None
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    pagination: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderConfig":
        return cls(
            name=value["name"],
            enabled=bool(value.get("enabled", True)),
            display_name=value.get("display_name"),
            base_url=value["base_url"],
            region=value.get("region"),
            source_type=value.get("source_type"),
            refresh_interval_hours=value.get("refresh_interval_hours"),
            crawl_delay_seconds=float(value.get("crawl_delay_seconds", 2)),
            max_pages=value.get("max_pages"),
            max_retries=int(value.get("max_retries", 3)),
            timeout_seconds=int(value.get("timeout_seconds", 25)),
            rate_limit_per_minute=value.get("rate_limit_per_minute"),
            allowed_domains=list(value.get("allowed_domains") or []),
            blocked_domains=list(value.get("blocked_domains") or []),
            pagination=dict(value.get("pagination") or {}),
            validation=dict(value.get("validation") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "display_name": self.display_name,
            "base_url": self.base_url,
            "region": self.region,
            "source_type": self.source_type,
            "refresh_interval_hours": self.refresh_interval_hours,
            "crawl_delay_seconds": self.crawl_delay_seconds,
            "max_pages": self.max_pages,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "allowed_domains": self.allowed_domains,
            "blocked_domains": self.blocked_domains,
            "pagination": self.pagination,
            "validation": self.validation,
        }


def load_provider_configs(path: Path = DEFAULT_PROVIDER_CONFIG) -> list[ProviderConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [ProviderConfig.from_dict(item) for item in data.get("providers", [])]


def sync_provider_configs(session: Session, configs: list[ProviderConfig] | None = None) -> None:
    configs = configs or load_provider_configs()
    for config in configs:
        source = session.query(SourceProvider).filter(SourceProvider.name == config.name).one_or_none()
        payload = config.to_dict()
        if source is None:
            source = SourceProvider(name=config.name, base_url=config.base_url)
            session.add(source)
        source.enabled = config.enabled
        source.display_name = config.display_name
        source.base_url = config.base_url
        source.region = config.region
        source.source_type = config.source_type
        source.refresh_interval_hours = config.refresh_interval_hours
        source.crawl_delay_seconds = config.crawl_delay_seconds
        source.max_pages = config.max_pages
        source.max_retries = config.max_retries
        source.timeout_seconds = config.timeout_seconds
        source.rate_limit_per_minute = config.rate_limit_per_minute
        source.config_json = json.dumps(payload, indent=2, sort_keys=True)
    session.commit()
