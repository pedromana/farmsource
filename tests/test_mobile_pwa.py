from fastapi.testclient import TestClient

from app.main import app


def login_driver(client: TestClient) -> None:
    response = client.post("/driver/login", data={"email": "driver@example.com", "password": "Driver123!"}, follow_redirects=False)
    assert response.status_code == 303


def test_pwa_manifest_and_service_worker_are_ready() -> None:
    with TestClient(app) as client:
        manifest = client.get("/static/manifest.json")
        assert manifest.status_code == 200
        data = manifest.json()
        assert data["name"] == "Farmsource"
        assert data["display"] == "standalone"
        assert data["start_url"] == "/customer/catalog"
        assert data["icons"]
        assert any(shortcut["url"] == "/driver/routes" for shortcut in data["shortcuts"])

        service_worker = client.get("/static/js/service-worker.js")
        assert service_worker.status_code == 200
        assert "CACHE_NAME" in service_worker.text
        assert "fetch" in service_worker.text


def test_customer_mobile_app_markup_loads() -> None:
    with TestClient(app) as client:
        response = client.get("/customer/catalog")
        assert response.status_code == 200
        assert "mobile-app-nav" in response.text
        assert "customer-mobile-nav" in response.text
        assert "sticky-cart-cta" in response.text
        assert "app-page-bar" in response.text
        assert 'loading="lazy"' in response.text
        assert 'href="/driver/routes">Driver' not in response.text


def test_driver_mobile_app_markup_loads() -> None:
    with TestClient(app) as client:
        login_driver(client)
        routes = client.get("/driver/routes")
        assert routes.status_code == 200
        assert "driver-tabs" in routes.text
        assert "driver-mobile-nav" in routes.text
        assert "touch-button" in routes.text
        assert 'href="/customer/catalog">Shop' not in routes.text

        route_marker = '/driver/route/'
        assert route_marker in routes.text
        route_id = routes.text.split(route_marker, 1)[1].split('"', 1)[0]
        route = client.get(f"/driver/route/{route_id}")
        assert route.status_code == 200
        assert 'href="#stops"' in route.text
        assert "<summary>Decline route</summary>" in route.text
