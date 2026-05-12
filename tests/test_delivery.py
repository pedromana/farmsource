from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Driver, Route, RouteStop


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def login_driver(client: TestClient) -> None:
    response = client.post("/driver/login", data={"email": "driver@example.com", "password": "Driver123!"}, follow_redirects=False)
    assert response.status_code == 303


def test_admin_route_and_delivery_exports_load() -> None:
    with TestClient(app) as client:
        login_admin(client)
        for path in (
            "/admin/routes",
            "/admin/routes/new",
            "/admin/drivers",
            "/admin/exports/route-manifest",
            "/admin/exports/delivery-summary",
            "/admin/exports/driver-payouts",
            "/admin/exports/failed-deliveries",
        ):
            response = client.get(path)
            assert response.status_code == 200


def test_admin_route_suggestion_can_be_accepted() -> None:
    with TestClient(app) as client:
        login_admin(client)
        response = client.post("/admin/routes/suggestions/accept-all", follow_redirects=False)
        assert response.status_code == 303

    with SessionLocal() as db:
        route = db.query(Route).filter(Route.route_name == "Seattle Pilot Route").first()
        driver = db.query(Driver).filter(Driver.email == "driver@example.com").first()
        assert route is not None
        assert driver is not None
        assert route.driver_id == driver.id


def test_admin_can_unassign_route_from_driver() -> None:
    with TestClient(app) as client:
        login_admin(client)
        client.post("/admin/routes/suggestions/accept-all", follow_redirects=False)
        with SessionLocal() as db:
            route = db.query(Route).filter(Route.route_name == "Seattle Pilot Route").first()
            assert route is not None
            route_id = route.id

        response = client.post(f"/admin/routes/{route_id}/unassign-driver", follow_redirects=False)
        assert response.status_code == 303

    with SessionLocal() as db:
        route = db.get(Route, route_id)
        driver = db.query(Driver).filter(Driver.email == "driver@example.com").first()
        assert route is not None
        assert driver is not None
        assert route.driver_id is None
        assert route.route_status == "planned"
        route.driver_id = driver.id
        route.route_status = "assigned"
        route.reassignment_priority = False
        db.commit()


def test_driver_can_decline_route_and_route_becomes_priority() -> None:
    with TestClient(app) as client:
        login_admin(client)
        client.post("/admin/routes/suggestions/accept-all", follow_redirects=False)
        login_driver(client)

        with SessionLocal() as db:
            route = db.query(Route).filter(Route.route_name == "Seattle Pilot Route").first()
            assert route is not None
            route_id = route.id

        decline_response = client.post(
            f"/driver/route/{route_id}/decline",
            data={"decline_reason": "Schedule conflict"},
            follow_redirects=False,
        )
        assert decline_response.status_code == 303

        routes_response = client.get("/driver/routes")
        assert routes_response.status_code == 200
        assert "Seattle Pilot Route" not in routes_response.text

    with SessionLocal() as db:
        route = db.get(Route, route_id)
        driver = db.query(Driver).filter(Driver.email == "driver@example.com").first()
        assert route is not None
        assert driver is not None
        assert route.driver_id is None
        assert route.reassignment_priority is True
        assert "Declined by" in (route.assignment_notes or "")
        route.driver_id = driver.id
        route.route_status = "assigned"
        route.reassignment_priority = False
        route.assignment_notes = None
        db.commit()


def test_driver_route_workflow_loads_and_updates_stop() -> None:
    with TestClient(app) as client:
        bad_login = client.post("/driver/login", data={"email": "driver@example.com", "password": "wrong"})
        assert bad_login.status_code == 400
        login_driver(client)
        routes_response = client.get("/driver/routes")
        assert routes_response.status_code == 200
        assert "Seattle Pilot Route" in routes_response.text

        with SessionLocal() as db:
            driver = db.query(Driver).filter(Driver.email == "driver@example.com").first()
            assert driver is not None
            route = driver.routes[0]
            stop = route.stops[0]
            route_id = route.id
            stop_id = stop.id

        route_response = client.get(f"/driver/route/{route_id}")
        assert route_response.status_code == 200

        stop_response = client.get(f"/driver/stop/{stop_id}")
        assert stop_response.status_code == 200

        update_response = client.post(
            f"/driver/stop/{stop_id}",
            data={"action_status": "delivered", "driver_notes": "Left at door.", "failed_reason": "", "proof_of_delivery_url": ""},
            follow_redirects=False,
        )
        assert update_response.status_code == 303

    with SessionLocal() as db:
        stop = db.get(RouteStop, stop_id)
        assert stop is not None
        assert stop.stop_status == "delivered"
        assert stop.order.order_status == "delivered"
        stop.stop_status = "pending"
        stop.driver_notes = None
        stop.delivered_at = None
        stop.order.order_status = "assigned_to_route"
        db.commit()
