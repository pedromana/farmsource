from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Producer


def test_admin_pages_load() -> None:
    with TestClient(app) as client:
        for path in ("/admin", "/admin/sources", "/admin/imports", "/admin/producers"):
            response = client.get(path)
            assert response.status_code == 200


def test_csv_import_classifies_and_lists_producer() -> None:
    _delete_test_producer()
    csv_content = (
        "farm_name,city,state,shop_url,products\n"
        "Test Phase Two Farm,Seattle,WA,https://example.myshopify.com,vegetables\n"
    )

    with TestClient(app) as client:
        response = client.post(
            "/admin/imports",
            data={"source_id": ""},
            files={"file": ("phase-two-producers.csv", csv_content, "text/csv")},
            follow_redirects=False,
        )

        assert response.status_code == 303

        producers = client.get("/admin/producers?product=vegetables")
        assert producers.status_code == 200
        assert "Test Phase Two Farm" in producers.text
        assert "Shopify" in producers.text

    _delete_test_producer()


def test_producer_export_returns_excel() -> None:
    with TestClient(app) as client:
        response = client.get("/admin/producers/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _delete_test_producer() -> None:
    with SessionLocal() as db:
        rows = db.query(Producer).filter(Producer.producer_name == "Test Phase Two Farm").all()
        for row in rows:
            db.delete(row)
        db.commit()
