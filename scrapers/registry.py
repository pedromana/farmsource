from __future__ import annotations

from importlib import import_module

from app.provider_config import ProviderConfig
from scrapers.base import BaseProvider

PROVIDER_CLASSES = {
    "wa_food_farm_finder": "scrapers.providers.wa_food_farm_finder.provider:WAFoodFarmFinderProvider",
    "localharvest": "scrapers.providers.localharvest.provider:LocalHarvestProvider",
    "marketwagon": "scrapers.providers.marketwagon.provider:MarketWagonProvider",
    "grownby": "scrapers.providers.grownby.provider:GrownByProvider",
}


def provider_for(config: ProviderConfig) -> BaseProvider:
    dotted = PROVIDER_CLASSES.get(config.name)
    if not dotted:
        dotted = f"scrapers.providers.{config.name}.provider:Provider"
    module_name, class_name = dotted.split(":")
    module = import_module(module_name)
    provider_class = getattr(module, class_name)
    return provider_class(config)
