from app.services.classification import classify_producer_destination


def test_social_media_is_not_qualified() -> None:
    result = classify_producer_destination(None, "https://instagram.com/examplefarm")

    assert result.destination_type == "social_media_page"
    assert result.qualified is False


def test_platform_store_is_qualified() -> None:
    result = classify_producer_destination(None, "https://example.myshopify.com")

    assert result.destination_type == "ecommerce_store"
    assert result.platform_detected == "Shopify"
    assert result.qualified is True
