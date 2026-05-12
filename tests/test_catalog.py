from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Product
from app.services.catalog import active_delivery_window, active_product_query, remaining_inventory


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_seeded_catalog_pages_load() -> None:
    with TestClient(app) as client:
        login_admin(client)
        for path in (
            "/admin/categories",
            "/admin/products",
            "/admin/products/new",
            "/admin/availability",
            "/customer/catalog",
        ):
            response = client.get(path)
            assert response.status_code == 200


def test_customer_product_and_category_pages_load() -> None:
    with TestClient(app) as client:
        with SessionLocal() as db:
            product = db.query(Product).filter(Product.active.is_(True)).first()
            assert product is not None
            product_id = product.id
            category_id = product.category_id

        product_response = client.get(f"/customer/product/{product_id}")
        assert product_response.status_code == 200

        category_response = client.get(f"/customer/category/{category_id}")
        assert category_response.status_code == 200


def test_catalog_availability_helpers() -> None:
    with TestClient(app):
        with SessionLocal() as db:
            window = active_delivery_window(db)
            assert window is not None
            product = db.scalars(active_product_query(window.id)).first()
            assert product is not None
            assert remaining_inventory(product.availability[0]) > 0


def test_product_exports_return_excel() -> None:
    with TestClient(app) as client:
        login_admin(client)
        for path in ("/admin/products/export", "/admin/availability/export"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
