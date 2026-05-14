CTA_BY_AUDIENCE = {
    "customers": "Join the waitlist for fresh local food in your neighborhood.",
    "producers": "Tell us what you grow and how Farmsource can help you reach nearby customers.",
    "drivers": "Apply to run planned local delivery routes.",
    "general": "Follow Farmsource for local food launch updates.",
}


def generate_caption(title: str, content_theme: str | None, target_audience: str, target_platform: str) -> str:
    theme = content_theme or "local food"
    cta = CTA_BY_AUDIENCE.get(target_audience, CTA_BY_AUDIENCE["general"])
    platform_note = "short vertical story" if target_platform in {"instagram", "tiktok", "youtube_shorts"} else "community update"
    return (
        f"{title}\n\n"
        f"Fresh, seasonal, and local: this {platform_note} highlights {theme.lower()} through the Farmsource scheduled delivery model. "
        "Built for neighbors who want farm-quality produce without another grocery run.\n\n"
        f"{cta}"
    )


def generate_call_to_action(target_audience: str) -> str:
    return CTA_BY_AUDIENCE.get(target_audience, CTA_BY_AUDIENCE["general"])
