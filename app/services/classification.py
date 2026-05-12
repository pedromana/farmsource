from dataclasses import dataclass
from urllib.parse import urlparse


SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
)

PLATFORM_INDICATORS = {
    "Shopify": ("shopify", "myshopify.com"),
    "Square": ("square.site", "squareup.com", "weebly.com"),
    "Barn2Door": ("barn2door",),
    "Harvie": ("harvie",),
    "GrownBy": ("grownby", "grownby.app"),
    "Local Line": ("localline", "local-line"),
    "WooCommerce": ("woocommerce", "wc-ajax"),
    "GrazeCart": ("grazecart",),
    "Farmigo": ("farmigo",),
    "Stripe": ("stripe",),
    "PayPal": ("paypal",),
}


@dataclass(frozen=True)
class ClassificationResult:
    destination_type: str
    platform_detected: str | None
    confidence_score: float
    online_ordering_confirmed: bool
    qualified: bool
    reason: str


def classify_producer_destination(
    website_url: str | None,
    online_order_url: str | None,
) -> ClassificationResult:
    target_url = _clean_url(online_order_url) or _clean_url(website_url)
    if not target_url:
        return ClassificationResult("unknown", None, 0.0, False, False, "No destination URL provided.")

    domain = _domain(target_url)
    url_text = target_url.lower()

    if _is_social_domain(domain):
        return ClassificationResult(
            "social_media_page",
            None,
            0.95,
            False,
            False,
            "Destination is a social media page and is excluded from qualification.",
        )

    platform = _detect_platform(url_text)
    if platform:
        destination_type = "farm_platform_store" if platform in {"Barn2Door", "Harvie", "GrownBy", "Local Line", "GrazeCart", "Farmigo"} else "ecommerce_store"
        return ClassificationResult(
            destination_type,
            platform,
            0.9,
            True,
            True,
            f"Detected {platform} ordering or payment platform indicator.",
        )

    if any(token in url_text for token in ("csa", "share-signup", "farm-share")):
        return ClassificationResult("csa_signup", None, 0.78, True, True, "URL suggests CSA signup.")

    if any(token in url_text for token in ("subscription", "subscribe", "box")):
        return ClassificationResult("subscription_box", None, 0.74, True, True, "URL suggests subscription ordering.")

    if any(token in url_text for token in ("shop", "store", "order", "cart", "checkout", "market")):
        return ClassificationResult("ecommerce_store", None, 0.72, True, True, "URL contains ecommerce ordering language.")

    if any(token in url_text for token in ("contact", "mailto:", "tel:")):
        return ClassificationResult("contact_only", None, 0.58, False, False, "Destination appears to be contact-oriented.")

    if website_url:
        return ClassificationResult("informational_page", None, 0.45, False, False, "Website found, but no ordering indicator detected.")

    return ClassificationResult("unknown", None, 0.2, False, False, "Destination could not be classified.")


def _clean_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value or None


def _domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def _is_social_domain(domain: str) -> bool:
    return any(domain == social or domain.endswith(f".{social}") for social in SOCIAL_DOMAINS)


def _detect_platform(url_text: str) -> str | None:
    for platform, indicators in PLATFORM_INDICATORS.items():
        if any(indicator in url_text for indicator in indicators):
            return platform
    return None
