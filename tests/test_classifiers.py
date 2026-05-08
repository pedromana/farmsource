from scrapers.common.classifiers import classify_destination


def test_social_media_is_excluded() -> None:
    result = classify_destination("https://facebook.com/examplefarm", "<html></html>", 200)

    assert result.destination_type == "social_media_page"
    assert result.online_ordering_confirmed is False


def test_shopify_checkout_qualifies() -> None:
    html = """
    <html>
      <head><script src="https://cdn.shopify.com/storefront.js"></script></head>
      <body><button>Add to cart</button><a href="/checkout">Checkout</a></body>
    </html>
    """
    result = classify_destination("https://examplefarm.com/shop", html, 200)

    assert result.destination_type == "ecommerce_store"
    assert result.online_ordering_confirmed is True
    assert result.confidence_score >= 50


def test_contact_only_does_not_qualify() -> None:
    html = "<html><body><h1>Example Farm</h1><a>Contact us</a><p>Email us for availability.</p></body></html>"
    result = classify_destination("https://examplefarm.com", html, 200)

    assert result.destination_type == "contact_only"
    assert result.online_ordering_confirmed is False
