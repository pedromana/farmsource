from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DeliveryWindow, Order
from app.config import get_settings
from app.services.catalog import active_product_query


def test_customer_cart_checkout_local_payment_flow(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    get_settings.cache_clear()
    with TestClient(app) as client:
        with SessionLocal() as db:
            product = db.scalars(active_product_query()).first()
            window = db.query(DeliveryWindow).filter(DeliveryWindow.active.is_(True)).first()
            assert product is not None
            assert window is not None
            product_id = product.id
            window_id = window.id

        add_response = client.post(
            "/customer/cart/add",
            data={"product_id": product_id, "quantity": 1},
            follow_redirects=False,
        )
        assert add_response.status_code == 303

        cart_response = client.get("/customer/cart")
        assert cart_response.status_code == 200
        assert "Your cart" in cart_response.text

        checkout_response = client.get("/customer/checkout")
        assert checkout_response.status_code == 200

        pay_response = client.post(
            "/customer/checkout",
            data={
                "first_name": "Phase",
                "last_name": "Four",
                "email": "phase4@example.com",
                "phone": "206-555-0101",
                "address_line_1": "456 Pine St",
                "address_line_2": "",
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "delivery_window_id": str(window_id),
                "delivery_notes": "",
                "customer_notes": "",
            },
            follow_redirects=False,
        )
        assert pay_response.status_code == 303
        assert "/customer/payment-success" in pay_response.headers["location"]

        success_response = client.get(pay_response.headers["location"], follow_redirects=True)
        assert success_response.status_code == 200
        assert "Thanks for your order" in success_response.text

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.customer.has(email="phase4@example.com")).order_by(Order.id.desc()).first()
        assert order is not None
        assert order.payment_status == "paid"
        assert order.order_status == "confirmed"
    get_settings.cache_clear()


def test_order_lookup_page_loads() -> None:
    with TestClient(app) as client:
        response = client.get("/customer/orders?email=sample.customer@example.com")
        assert response.status_code == 200


def test_ajax_cart_add_and_update_returns_live_totals() -> None:
    with TestClient(app) as client:
        with SessionLocal() as db:
            product = db.scalars(active_product_query()).first()
            assert product is not None
            product_id = product.id

        add_response = client.post(
            "/customer/cart/add",
            data={"product_id": product_id, "quantity": 1},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert add_response.status_code == 200
        payload = add_response.json()
        assert payload["count"] >= 1
        item_id = payload["items"][0]["id"]

        update_response = client.post(
            "/customer/cart/update",
            data={"item_id": item_id, "quantity": 2},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["count"] >= 2
