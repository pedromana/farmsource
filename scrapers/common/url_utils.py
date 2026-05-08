from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

SOCIAL_MEDIA_DOMAINS = {
    "facebook.com",
    "fb.com",
    "instagram.com",
    "tiktok.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
}


def normalize_url(url: str | None, base_url: str | None = None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if base_url:
        url = urljoin(base_url, url)
    parsed = urlparse(url)
    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", urlencode(query_pairs), ""))


def domain_for(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_social_media_url(url: str | None, extra_blocked_domains: list[str] | None = None) -> bool:
    domain = domain_for(url)
    blocked = set(SOCIAL_MEDIA_DOMAINS)
    blocked.update((extra_blocked_domains or []))
    return any(domain == item or domain.endswith(f".{item}") for item in blocked)
