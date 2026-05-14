import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal, check_database
from app.main import app
from app.models import DeliveryWindow, Driver, Order, Producer, Product, ProductAvailability, ProductCategory, Route, RouteStop
from app.services.cart import add_to_cart, get_or_create_cart
from app.services.catalog import active_product_query
from app.services.csv_importer import import_producers_from_csv
from app.services.delivery import ROUTE_STATUSES, STOP_STATUSES
from app.services.orders import ORDER_STATUSES, PAYMENT_STATUSES, available_delivery_windows, create_pending_order, mark_order_paid
from app.services.payments import create_checkout_session


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def login_driver(client: TestClient) -> None:
    response = client.post(
        "/driver/login",
        data={"email": "driver@example.com", "password": "Driver123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_database_connection_is_available() -> None:
    assert check_database() is True


def test_status_sets_match_v1_contract() -> None:
    assert ORDER_STATUSES == {"pending", "confirmed", "packed", "assigned_to_route", "out_for_delivery", "delivered", "cancelled"}
    assert PAYMENT_STATUSES == {"unpaid", "pending", "paid", "failed", "refunded"}
    assert ROUTE_STATUSES == {"planned", "assigned", "in_progress", "completed", "cancelled"}
    assert STOP_STATUSES == {"pending", "delivered", "failed", "skipped"}


def test_duplicate_producer_import_is_skipped() -> None:
    producer_name = f"Pytest Duplicate Farm {uuid4().hex[:8]}"
    csv_content = (
        "farm_name,city,state,shop_url,products\n"
        f"{producer_name},Seattle,WA,https://example.com/{producer_name.replace(' ', '-').lower()},vegetables\n"
    ).encode()

    with SessionLocal() as db:
        first = import_producers_from_csv(db, None, "duplicate-producer.csv", csv_content)
        second = import_producers_from_csv(db, None, "duplicate-producer.csv", csv_content)
        assert first.imported_rows == 1
        assert second.imported_rows == 0
        assert second.skipped_rows == 1

        for producer in db.query(Producer).filter(Producer.producer_name == producer_name).all():
            db.delete(producer)
        db.commit()


def test_admin_can_create_product_category_and_product() -> None:
    suffix = uuid4().hex[:8]

    with TestClient(app) as client:
        login_admin(client)
        category_response = client.post(
            "/admin/categories",
            data={"name": f"Readiness Category {suffix}", "description": "Pytest category", "active": "on"},
            follow_redirects=False,
        )
        assert category_response.status_code == 303

    with SessionLocal() as db:
        category = db.query(ProductCategory).filter(ProductCategory.name == f"Readiness Category {suffix}").first()
        assert category is not None

        product = Product(
            category_id=category.id,
            name=f"Readiness Product {suffix}",
            sku=f"READINESS-{suffix.upper()}",
            unit="each",
            price=4.5,
            active=True,
            delivery_eligible=True,
        )
        db.add(product)
        db.commit()
        assert db.query(Product).filter(Product.sku == f"READINESS-{suffix.upper()}").first() is not None

        db.delete(product)
        db.delete(category)
        db.commit()


def test_delivery_window_capacity_blocks_new_orders() -> None:
    with SessionLocal() as db:
        product = db.scalars(active_product_query()).first()
        window = db.query(DeliveryWindow).filter(DeliveryWindow.active.is_(True)).first()
        assert product is not None
        assert window is not None

        original_count = window.current_order_count
        original_max = window.max_orders
        window.current_order_count = window.max_orders
        db.commit()

        cart = get_or_create_cart(db, f"capacity-{uuid4().hex}")
        add_to_cart(db, cart, product.id, 1)
        db.refresh(cart)

        with pytest.raises(ValueError, match="Delivery window is full"):
            create_pending_order(db, cart, window.id, _customer_payload(f"capacity-{uuid4().hex[:8]}@example.com"))

        window.current_order_count = original_count
        window.max_orders = original_max
        db.commit()


def test_mocked_stripe_checkout_session_creation(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    get_settings.cache_clear()

    def fake_session_create(**kwargs):
        assert kwargs["mode"] == "payment"
        assert kwargs["line_items"]
        assert kwargs["success_url"].startswith("http://testserver/customer/payment-success")
        return SimpleNamespace(id="cs_test_mock", url="https://checkout.stripe.test/session")

    monkeypatch.setattr("app.services.payments.stripe.checkout.Session.create", fake_session_create)

    with SessionLocal() as db:
        order = _create_test_order(db, f"stripe-{uuid4().hex[:8]}@example.com")
        checkout_url = create_checkout_session(db, order)
        db.refresh(order)
        assert checkout_url == "https://checkout.stripe.test/session"
        assert order.stripe_checkout_session_id == "cs_test_mock"

    get_settings.cache_clear()


def test_marketing_content_export_returns_excel() -> None:
    with TestClient(app) as client:
        login_admin(client)
        response = client.get("/admin/exports/marketing-content")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_compact_v1_order_to_delivery_workflow(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    get_settings.cache_clear()
    email = f"pilot-flow-{uuid4().hex[:8]}@example.com"
    route_name = f"Pytest Pilot Route {uuid4().hex[:8]}"

    with TestClient(app) as client:
        with SessionLocal() as db:
            product = db.scalars(active_product_query()).first()
            window = available_delivery_windows(db)[0]
            driver = db.query(Driver).filter(Driver.email == "driver@example.com").first()
            assert product is not None
            assert driver is not None
            product_id = product.id
            window_id = window.id
            driver_id = driver.id

        add_response = client.post("/customer/cart/add", data={"product_id": product_id, "quantity": 1}, follow_redirects=False)
        assert add_response.status_code == 303
        checkout_response = client.post(
            "/customer/checkout",
            data={
                **_customer_payload(email),
                "delivery_window_id": str(window_id),
                "customer_notes": "Pilot readiness test order.",
            },
            follow_redirects=False,
        )
        assert checkout_response.status_code == 303
        assert "/customer/payment-success" in checkout_response.headers["location"]
        success_response = client.get(checkout_response.headers["location"], follow_redirects=True)
        assert success_response.status_code == 200

        with SessionLocal() as db:
            order = db.query(Order).filter(Order.customer.has(email=email)).order_by(Order.id.desc()).first()
            assert order is not None
            assert order.order_status == "confirmed"
            order_id = order.id

        login_admin(client)
        route_response = client.post(
            "/admin/routes",
            data={
                "route_name": route_name,
                "delivery_window_id": str(window_id),
                "driver_id": "",
                "region": "Seattle",
                "route_status": "planned",
                "estimated_start_time": "4:00 PM",
                "estimated_end_time": "7:00 PM",
                "estimated_stop_count": "0",
                "estimated_order_count": "0",
                "route_pay": "45",
                "route_bonus": "0",
                "assignment_notes": "",
                "route_notes": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert route_response.status_code == 303
        route_id = int(re.search(r"/admin/routes/(\d+)", route_response.headers["location"]).group(1))

        stop_response = client.post(f"/admin/routes/{route_id}/stops", data={"order_id": str(order_id)}, follow_redirects=False)
        assert stop_response.status_code == 303

        assign_response = client.post(
            f"/admin/routes/{route_id}/assign-driver",
            data={"driver_id": str(driver_id)},
            follow_redirects=False,
        )
        assert assign_response.status_code == 303

        login_driver(client)
        route_page = client.get(f"/driver/route/{route_id}")
        assert route_page.status_code == 200

        with SessionLocal() as db:
            stop = db.query(RouteStop).filter(RouteStop.route_id == route_id, RouteStop.order_id == order_id).first()
            assert stop is not None
            stop_id = stop.id

        delivered_response = client.post(
            f"/driver/stop/{stop_id}",
            data={"action_status": "delivered", "driver_notes": "Delivered during pilot readiness test.", "failed_reason": "", "proof_of_delivery_url": ""},
            follow_redirects=False,
        )
        assert delivered_response.status_code == 303

    with SessionLocal() as db:
        order = db.get(Order, order_id)
        route = db.get(Route, route_id)
        assert order is not None
        assert route is not None
        assert order.order_status == "delivered"
        assert route.route_status == "completed"

    get_settings.cache_clear()


def _create_test_order(db, email: str) -> Order:
    product = db.scalars(active_product_query()).first()
    window = available_delivery_windows(db)[0]
    assert product is not None
    cart = get_or_create_cart(db, f"order-{uuid4().hex}")
    add_to_cart(db, cart, product.id, 1)
    db.refresh(cart)
    order = create_pending_order(db, cart, window.id, _customer_payload(email))
    mark_order_paid(db, order, "pi_test_mock")
    return order


def _customer_payload(email: str) -> dict[str, str]:
    return {
        "first_name": "Pilot",
        "last_name": "Tester",
        "email": email,
        "phone": "206-555-0199",
        "address_line_1": "500 Pike St",
        "address_line_2": "",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98101",
        "delivery_notes": "",
    }
