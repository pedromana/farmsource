from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models import MarketingContent, MarketingContentSchedule
from app.services.ai_services.content_generator import generate_marketing_content


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"email": "admin@farmsource.local", "password": "ChangeMe123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_mock_marketing_generator_returns_complete_draft() -> None:
    generated = generate_marketing_content(
        "produce_box",
        "weekly produce boxes",
        "instagram",
        "customers",
        seed_title="Weekly Produce Box Preview",
        notes="Focus on colorful seasonal produce.",
    )
    assert "Weekly Produce Box Preview" in generated.title
    assert "CTA:" in generated.generated_caption
    assert "#Farmsource" in generated.generated_hashtags
    assert "vertical video" in generated.generated_video_prompt
    assert "0-2s" in generated.generated_script
    assert "Do not post automatically" in generated.ai_prompt


def test_admin_marketing_generation_approval_and_schedule_flow() -> None:
    _delete_test_marketing_content()
    with TestClient(app) as client:
        login_admin(client)
        dashboard = client.get("/admin/marketing")
        assert dashboard.status_code == 200
        assert "Marketing content" in dashboard.text

        create = client.post(
            "/admin/marketing",
            data={
                "title": "Test Berry Box Reel",
                "content_type": "produce_box",
                "content_theme": "weekly produce boxes",
                "target_platform": "instagram",
                "target_audience": "customers",
                "status": "draft",
                "scheduled_date": "2026-05-20T09:00",
                "notes": "Automated test draft.",
                "generate": "on",
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        detail_path = create.headers["location"]

        detail = client.get(detail_path)
        assert detail.status_code == 200
        assert "Test Berry Box Reel" in detail.text
        assert "#Farmsource" in detail.text

        content_id = int(detail_path.rsplit("/", 1)[-1])
        approve = client.post(f"/admin/marketing/{content_id}/approve", follow_redirects=False)
        assert approve.status_code == 303

        calendar = client.get("/admin/marketing/calendar")
        assert calendar.status_code == 200
        assert "Test Berry Box Reel" in calendar.text

        drafts = client.get("/admin/marketing/drafts")
        assert drafts.status_code == 200

    with SessionLocal() as db:
        content = db.query(MarketingContent).filter(MarketingContent.title == "Test Berry Box Reel").first()
        assert content is not None
        assert content.status == "approved"
        assert content.approved is True
        assert content.generated_caption
        schedule = db.query(MarketingContentSchedule).filter(MarketingContentSchedule.marketing_content_id == content.id).first()
        assert schedule is not None
        assert schedule.posting_platform == "instagram"
        assert schedule.posting_status == "planned"
    _delete_test_marketing_content()


def test_marketing_manual_posting_route_marks_content_posted() -> None:
    _delete_test_marketing_content("Test Manual Posted")
    with TestClient(app) as client:
        login_admin(client)
        create = client.post(
            "/admin/marketing",
            data={
                "title": "Test Manual Posted",
                "content_type": "delivery_content",
                "content_theme": "farm-to-door delivery",
                "target_platform": "facebook",
                "target_audience": "general",
                "status": "approved",
                "scheduled_date": "2026-05-21T12:00",
                "approved": "on",
                "generate": "on",
            },
            follow_redirects=False,
        )
        content_id = int(create.headers["location"].rsplit("/", 1)[-1])
        posted = client.post(f"/admin/marketing/{content_id}/mark-posted", follow_redirects=False)
        assert posted.status_code == 303

    with SessionLocal() as db:
        content = db.get(MarketingContent, content_id)
        assert content is not None
        assert content.status == "posted"
        assert content.schedules[0].posting_status == "posted"
    _delete_test_marketing_content("Test Manual Posted")


def _delete_test_marketing_content(title: str = "Test Berry Box Reel") -> None:
    init_db()
    with SessionLocal() as db:
        for content in db.query(MarketingContent).filter(MarketingContent.title == title).all():
            db.delete(content)
        db.commit()
