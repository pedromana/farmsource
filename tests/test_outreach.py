from fastapi.testclient import TestClient
from uuid import uuid4

import pytest

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.main import app
from app.models import Producer, ProducerOutreachCandidate, Source
from app.services.outreach import _extract_social_url


def test_social_url_extraction_normalizes_profiles() -> None:
    text = (
        "Follow https://www.instagram.com/example_farm/ and "
        "https://www.facebook.com/people/Example-Farm/100064768628450/?ref=page"
    )
    assert _extract_social_url(text, "instagram") == "https://www.instagram.com/example_farm/"
    assert _extract_social_url(text, "facebook") == "https://www.facebook.com/people/Example-Farm/100064768628450/"


def test_outreach_csv_import_ranks_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    init_db()
    suffix = uuid4().hex[:8]
    source_name = f"Pytest Outreach Source {suffix}"
    good_name = f"Pytest Organic Farm {suffix} LLC"
    hoa_name = f"Pytest Farm HOA {suffix}"
    oregon_name = f"Pytest Oregon Farm {suffix} LLC"
    with SessionLocal() as db:
        for name in (good_name, hoa_name, oregon_name):
            for producer in db.query(Producer).filter(Producer.producer_name == name).all():
                db.delete(producer)
        db.commit()

    def fake_research(candidate):
        if candidate.research_status in ("found_contact", "no_contact_found", "verified"):
            return candidate
        candidate.research_status = "no_contact_found"
        candidate.next_step = "No reliable public contact found."
        return candidate

    monkeypatch.setattr("app.routes.admin.research_candidate_now", fake_research)
    monkeypatch.setattr("app.services.outreach.research_candidate_now", fake_research)

    try:
        csv_content = (
            "Business Name,UBI#,Business Type,Principal Office Address,Registered Agent Name,Status\n"
            f"{good_name},111 222 333,WA LIMITED LIABILITY COMPANY,"
            "\"123 Farm Rd, SNOHOMISH, WA, 98290, UNITED STATES\",Test Agent,Active\n"
            f"{hoa_name},444 555 666,WA NONPROFIT CORPORATION,"
            "\"10 Condo Ln, SEATTLE, WA, 98101, UNITED STATES\",Other Agent,Active\n"
            f"{oregon_name},777 888 999,WA LIMITED LIABILITY COMPANY,"
            "\"10 Road, PORTLAND, OR, 97201, UNITED STATES\",Agent,Active\n"
        )
        client = TestClient(app)
        client.post(
            "/admin/login",
            data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
            follow_redirects=False,
        )
        response = client.post(
            "/admin/outreach/import",
            data={
                "source_name": source_name,
                "region": "seattle",
                "active_status_only": "on",
                "state_filter": "WA",
            },
            files={"file": ("outreach.csv", csv_content, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        page = client.get("/admin/outreach")
        assert good_name in page.text
        assert hoa_name not in page.text
        assert oregon_name not in page.text

        with SessionLocal() as db:
            candidate = db.query(ProducerOutreachCandidate).filter(ProducerOutreachCandidate.producer_name == good_name).first()
            assert candidate is not None
            candidate_id = candidate.id

        research = client.post(f"/admin/outreach/candidates/{candidate_id}/research")
        assert research.status_code == 200
        payload = research.json()
        assert payload["candidate"]["research_status"] == "no_contact_found"
        assert payload["progress"]["total"] >= 1

        progress = client.get("/admin/outreach/progress?region=seattle")
        assert progress.status_code == 200
        progress_payload = progress.json()
        assert "percent" in progress_payload
        assert "remaining" in progress_payload
        assert "found_contact" in progress_payload

        bulk = client.post("/admin/outreach/research-all", data={"region": "seattle", "research_status": "researching"})
        assert bulk.status_code == 200
        assert "researched" in bulk.json()

        with SessionLocal() as db:
            candidate = db.get(ProducerOutreachCandidate, candidate_id)
            candidate.contact_email = "pytest-farm@example.com"
            candidate.research_status = "found_contact"
            db.commit()
        repeat_research = client.post(f"/admin/outreach/candidates/{candidate_id}/research")
        assert repeat_research.status_code == 200
        repeat_payload = repeat_research.json()
        assert repeat_payload["candidate"]["research_status"] == "found_contact"
        assert repeat_payload["already_completed"] is True

        draft = client.get(f"/admin/outreach/candidates/{candidate_id}/email-suggestion")
        assert draft.status_code == 200
        assert "pytest-farm@example.com" in draft.text
        assert "Farmsource" in draft.text
        assert "Hello Test" not in draft.text
        assert "permission" not in draft.text.lower()
        assert "15-minute conversation" in draft.text
        assert "scheduled delivery channel" in draft.text
        assert "Open in Gmail" in draft.text
        assert "mail.google.com/mail/?view=cm" in draft.text
    finally:
        with SessionLocal() as db:
            source = db.query(Source).filter(Source.source_name == source_name).first()
            if source:
                db.query(ProducerOutreachCandidate).filter(ProducerOutreachCandidate.source_id == source.id).delete()
                db.delete(source)
            for name in (good_name, hoa_name, oregon_name):
                for producer in db.query(Producer).filter(Producer.producer_name == name).all():
                    db.delete(producer)
            db.commit()


def test_research_all_is_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    client = TestClient(app)
    client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    response = client.post("/admin/outreach/research-all", data={"region": "seattle"})
    assert response.status_code == 403
    get_settings.cache_clear()
