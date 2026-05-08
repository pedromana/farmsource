from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from scrapers.common.url_utils import is_social_media_url

QUALIFIED_TYPES = {"ecommerce_store", "csa_signup", "subscription_box", "farm_platform_store"}

PLATFORM_INDICATORS = {
    "Shopify": ["cdn.shopify.com", "myshopify.com", "shopify"],
    "Square": ["squareup.com", "square.site", "weebly.com", "square"],
    "Barn2Door": ["barn2door", "barn2door.com"],
    "Harvie": ["harvie", "harvie.farm"],
    "GrownBy": ["grownby", "grownby.app"],
    "Local Line": ["localline", "local line"],
    "WooCommerce": ["woocommerce", "wp-content/plugins/woocommerce"],
    "GrazeCart": ["grazecart"],
    "Farmigo": ["farmigo"],
    "Stripe checkout": ["checkout.stripe.com", "js.stripe.com"],
    "PayPal checkout": ["paypal.com/checkout", "paypalobjects.com"],
}

ORDERING_INDICATORS = [
    "add to cart",
    "checkout",
    "order online",
    "buy now",
    "shop now",
    "subscribe",
    "subscription",
    "purchase",
    "cart",
]

CSA_INDICATORS = ["csa signup", "csa sign up", "join our csa", "csa share", "weekly box"]
DELIVERY_INDICATORS = ["delivery available", "home delivery", "local delivery", "deliver to"]
PICKUP_INDICATORS = ["pickup available", "farm pickup", "local pickup", "pick up"]
CONTACT_ONLY_INDICATORS = ["contact us", "send message", "request information", "email us"]


@dataclass(slots=True)
class ClassificationResult:
    destination_type: str
    platform_detected: str | None
    online_ordering_confirmed: bool
    confidence_score: float
    classification_reason: str
    pickup_available: bool = False
    delivery_available: bool = False
    matched_indicators: list[str] = field(default_factory=list)


def classify_destination(
    url: str | None,
    html: str | None,
    status_code: int | None,
    blocked_domains: list[str] | None = None,
) -> ClassificationResult:
    if not url:
        return ClassificationResult("unknown", None, False, 0, "No destination URL was available.")
    if is_social_media_url(url, blocked_domains):
        return ClassificationResult("social_media_page", None, False, 0, "Destination is a blocked social media domain.")
    if status_code is None or status_code >= 400:
        return ClassificationResult("broken_link", None, False, 0, f"Destination returned status {status_code}.")

    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    markup = (html or "").lower()
    combined = f"{url.lower()} {text} {markup}"

    matched_platforms = [
        platform
        for platform, needles in PLATFORM_INDICATORS.items()
        if any(needle.lower() in combined for needle in needles)
    ]
    matched_ordering = [needle for needle in ORDERING_INDICATORS if needle in combined]
    matched_csa = [needle for needle in CSA_INDICATORS if needle in combined]
    pickup_available = any(needle in combined for needle in PICKUP_INDICATORS)
    delivery_available = any(needle in combined for needle in DELIVERY_INDICATORS)

    score = 0
    if matched_platforms:
        score += 45
    score += min(len(matched_ordering) * 12, 40)
    if matched_csa:
        score += 30
    if "checkout" in matched_ordering or "add to cart" in matched_ordering:
        score += 15
    score = min(score, 100)

    platform = ", ".join(matched_platforms) if matched_platforms else None
    matched = matched_platforms + matched_ordering + matched_csa

    if score >= 50 and matched_csa:
        destination_type = "csa_signup"
    elif score >= 50 and platform:
        destination_type = "farm_platform_store" if platform not in {"Shopify", "WooCommerce"} else "ecommerce_store"
    elif score >= 50:
        destination_type = "ecommerce_store"
    elif any(needle in combined for needle in CONTACT_ONLY_INDICATORS) and not matched_ordering:
        destination_type = "contact_only"
    elif text:
        destination_type = "informational_page"
    else:
        destination_type = "unknown"

    confirmed = destination_type in QUALIFIED_TYPES
    reason = (
        f"Matched {', '.join(matched)} with confidence {score}."
        if matched
        else "No strong ecommerce, CSA, checkout, cart, or subscription indicators were found."
    )
    return ClassificationResult(
        destination_type=destination_type,
        platform_detected=platform,
        online_ordering_confirmed=confirmed,
        confidence_score=score,
        classification_reason=reason,
        pickup_available=pickup_available,
        delivery_available=delivery_available,
        matched_indicators=matched,
    )
