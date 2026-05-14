BASE_HASHTAGS = {
    "customers": ["#FreshDelivery", "#HealthyEating", "#FarmToDoor"],
    "producers": ["#LocalFarms", "#FarmToTable", "#SupportLocalProducers"],
    "drivers": ["#DeliveryJobs", "#LocalRoutes", "#FlexibleWork"],
    "general": ["#LocalProduce", "#FarmToTable", "#FreshFood"],
}

THEME_HASHTAGS = {
    "fresh produce": ["#FreshProduce", "#SeasonalProduce"],
    "local farms": ["#LocalFarms", "#SeattleFarmers"],
    "weekly produce boxes": ["#ProduceBox", "#WeeklyHarvest"],
    "Seattle/local community": ["#SeattleFood", "#SeattleEats"],
    "farm-to-door delivery": ["#FarmToDoor", "#FreshDelivery"],
    "healthy meals": ["#HealthyEating", "#MealPrep"],
    "produce unboxing": ["#ProduceUnboxing", "#FarmBox"],
    "recipe inspiration": ["#RecipeInspiration", "#SeasonalCooking"],
    "driver recruitment": ["#DeliveryDrivers", "#RouteDelivery"],
    "producer recruitment": ["#FarmMarketing", "#SellLocal"],
}


def generate_hashtags(content_theme: str | None, target_audience: str) -> str:
    tags = list(BASE_HASHTAGS.get(target_audience, BASE_HASHTAGS["general"]))
    theme_key = (content_theme or "").strip()
    tags.extend(THEME_HASHTAGS.get(theme_key, []))
    tags.extend(["#Farmsource", "#LocalFood"])
    deduped = list(dict.fromkeys(tags))
    return " ".join(deduped[:10])
