from scrapers.common.url_utils import is_social_media_url, normalize_url


def test_normalize_url_removes_tracking() -> None:
    assert normalize_url("HTTPS://www.Example.com/shop/?utm_source=x&item=1") == "https://example.com/shop?item=1"


def test_social_media_subdomain_detected() -> None:
    assert is_social_media_url("https://m.instagram.com/example") is True
