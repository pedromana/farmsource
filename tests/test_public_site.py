from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DriverInterest, ProducerInterest, WaitlistSignup


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_public_marketing_pages_load() -> None:
    with TestClient(app) as client:
        for path in ("/", "/how-it-works", "/for-customers", "/for-producers", "/for-drivers", "/about", "/waitlist", "/contact", "/faq"):
            response = client.get(path)
            assert response.status_code == 200
            assert "Farmsource" in response.text
            assert "<meta name=\"description\"" in response.text


def test_public_forms_save_leads() -> None:
    _delete_public_test_leads()
    with TestClient(app) as client:
        waitlist = client.post(
            "/waitlist",
            data={"signup_type": "customer", "first_name": "Public", "email": "public.customer@example.com", "source_page": "/waitlist"},
            follow_redirects=False,
        )
        assert waitlist.status_code == 303

        producer = client.post(
            "/producer-interest",
            data={"business_name": "Public Farm", "contact_name": "Farmer One", "email": "public.producer@example.com"},
            follow_redirects=False,
        )
        assert producer.status_code == 303

        driver = client.post(
            "/driver-interest",
            data={"first_name": "Public", "email": "public.driver@example.com"},
            follow_redirects=False,
        )
        assert driver.status_code == 303

    with SessionLocal() as db:
        assert db.query(WaitlistSignup).filter(WaitlistSignup.email == "public.customer@example.com").first() is not None
        assert db.query(ProducerInterest).filter(ProducerInterest.email == "public.producer@example.com").first() is not None
        assert db.query(DriverInterest).filter(DriverInterest.email == "public.driver@example.com").first() is not None
    _delete_public_test_leads()


def test_admin_lead_pages_and_exports_load() -> None:
    with TestClient(app) as client:
        login_admin(client)
        for path in ("/admin/waitlist", "/admin/producers/interests", "/admin/drivers/interests"):
            response = client.get(path)
            assert response.status_code == 200
        for path in ("/admin/exports/waitlist", "/admin/exports/producer-interests", "/admin/exports/driver-interests"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _delete_public_test_leads() -> None:
    with SessionLocal() as db:
        for model, email in (
            (WaitlistSignup, "public.customer@example.com"),
            (ProducerInterest, "public.producer@example.com"),
            (DriverInterest, "public.driver@example.com"),
        ):
            row = db.query(model).filter(model.email == email).first()
            if row:
                db.delete(row)
        db.commit()
