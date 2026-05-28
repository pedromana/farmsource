from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import ContactMessage, DriverInterest, ProducerInterest, WaitlistSignup


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


PUBLIC_META = {
    "/": ("Farmsource | Nationwide Local Produce Delivery", "Fresh local produce directly from regional producers through scheduled neighborhood delivery routes across the United States."),
    "/how-it-works": ("How Farmsource Works | Scheduled Farm Delivery", "How Farmsource curates local produce and organizes scheduled neighborhood routes for communities nationwide."),
    "/for-customers": ("For Customers | Farmsource Local Produce Waitlist", "Join Farmsource for curated weekly produce, local farm sourcing, and scheduled regional delivery windows."),
    "/for-producers": ("For Producers | Sell Through Farmsource", "Reach nearby customers with Farmsource customer aggregation, curated offerings, and route-based delivery coordination."),
    "/for-drivers": ("For Drivers | Farmsource Route Delivery", "Predictable neighborhood delivery routes, guaranteed route pay, and community-focused work for Farmsource delivery regions."),
    "/about": ("About Farmsource | Local Food Routes", "Farmsource connects local producers, customers, and route drivers through a simple scheduled delivery model."),
    "/waitlist": ("Join the Farmsource Waitlist | Local Produce Delivery", "Join the Farmsource launch waitlist as a customer, producer, or driver in your region."),
    "/contact": ("Contact Farmsource | Local Produce Delivery", "Contact Farmsource about local produce delivery, producer onboarding, customer waitlists, or driver opportunities."),
    "/faq": ("Farmsource FAQ | Nationwide Local Produce Delivery", "Answers about Farmsource delivery windows, participating farms, producers, drivers, and regional launch plans."),
}
PUBLIC_PATHS = tuple(PUBLIC_META.keys())


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    return _temporary_landing_template(request, submitted=None)


@router.post("/launch-contact")
def submit_launch_contact(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
    reason: Annotated[str | None, Form()] = None,
):
    if not _required(name) or not _required(email):
        raise HTTPException(status_code=400, detail="Name and email are required")
    db.add(
        WaitlistSignup(
            signup_type="launch_contact",
            first_name=name.strip(),
            email=email.strip().lower(),
            phone=_optional(phone),
            notes=_optional(reason),
            source_page="/",
        )
    )
    db.commit()
    return RedirectResponse("/?submitted=contact", status_code=303)


@router.get("/how-it-works", response_class=HTMLResponse)
def how_it_works(request: Request) -> HTMLResponse:
    return _public_template(request, "public_how_it_works.html", "/how-it-works")


@router.get("/for-customers", response_class=HTMLResponse)
def for_customers(request: Request) -> HTMLResponse:
    return _public_template(request, "public_customers.html", "/for-customers")


@router.get("/for-producers", response_class=HTMLResponse)
def for_producers(request: Request, submitted: str | None = None) -> HTMLResponse:
    return _public_template(request, "public_producers.html", "/for-producers", {"submitted": submitted})


@router.get("/for-drivers", response_class=HTMLResponse)
def for_drivers(request: Request, submitted: str | None = None) -> HTMLResponse:
    return _public_template(request, "public_drivers.html", "/for-drivers", {"submitted": submitted})


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    return _public_template(request, "public_about.html", "/about")


@router.get("/waitlist", response_class=HTMLResponse)
def waitlist(request: Request, submitted: str | None = None) -> HTMLResponse:
    return _public_template(request, "public_waitlist.html", "/waitlist", {"submitted": submitted})


@router.get("/contact", response_class=HTMLResponse)
def contact(request: Request, submitted: str | None = None) -> HTMLResponse:
    return _public_template(request, "public_contact.html", "/contact", {"submitted": submitted})


@router.get("/faq", response_class=HTMLResponse)
def faq(request: Request) -> HTMLResponse:
    return _public_template(request, "public_faq.html", "/faq")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n"


@router.get("/sitemap.xml")
def sitemap_xml(request: Request) -> Response:
    base_url = str(request.base_url).rstrip("/")
    urls = "\n".join(
        f"  <url><loc>{base_url}{path}</loc><changefreq>weekly</changefreq><priority>{'1.0' if path == '/' else '0.8'}</priority></url>"
        for path in PUBLIC_PATHS
    )
    content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n'
    return Response(content=content, media_type="application/xml")


@router.get("/full-site", response_class=HTMLResponse)
def full_site_home(request: Request) -> HTMLResponse:
    return _public_template(request, "public_home.html", "/")


@router.get("/customer", response_class=HTMLResponse)
def customer_app(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("customer.html", {"request": request})


@router.post("/waitlist")
def submit_waitlist(
    db: Annotated[Session, Depends(get_db)],
    signup_type: Annotated[str, Form()],
    first_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    last_name: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    state: Annotated[str | None, Form()] = None,
    zip_code: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    source_page: Annotated[str | None, Form()] = None,
):
    if signup_type not in {"customer", "producer", "driver"}:
        raise HTTPException(status_code=400, detail="Invalid signup type")
    if not _required(first_name) or not _required(email):
        raise HTTPException(status_code=400, detail="First name and email are required")
    db.add(
        WaitlistSignup(
            signup_type=signup_type,
            first_name=first_name.strip(),
            last_name=_optional(last_name),
            email=email.strip().lower(),
            phone=_optional(phone),
            city=_optional(city),
            state=_optional(state),
            zip_code=_optional(zip_code),
            notes=_optional(notes),
            source_page=_optional(source_page),
        )
    )
    db.commit()
    return RedirectResponse(f"{source_page or '/waitlist'}?submitted=waitlist", status_code=303)


@router.post("/producer-interest")
def submit_producer_interest(
    db: Annotated[Session, Depends(get_db)],
    business_name: Annotated[str, Form()],
    contact_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
    website_url: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    state: Annotated[str | None, Form()] = None,
    products: Annotated[str | None, Form()] = None,
    delivery_capability: Annotated[str | None, Form()] = None,
    online_ordering: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    if not _required(business_name) or not _required(contact_name) or not _required(email):
        raise HTTPException(status_code=400, detail="Business name, contact name, and email are required")
    db.add(
        ProducerInterest(
            business_name=business_name.strip(),
            contact_name=contact_name.strip(),
            email=email.strip().lower(),
            phone=_optional(phone),
            website_url=_optional(website_url),
            city=_optional(city),
            state=_optional(state),
            products=_optional(products),
            delivery_capability=_optional(delivery_capability),
            online_ordering=_optional(online_ordering),
            notes=_optional(notes),
        )
    )
    db.commit()
    return RedirectResponse("/for-producers?submitted=producer", status_code=303)


@router.post("/driver-interest")
def submit_driver_interest(
    db: Annotated[Session, Depends(get_db)],
    first_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    last_name: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    state: Annotated[str | None, Form()] = None,
    vehicle_type: Annotated[str | None, Form()] = None,
    availability_notes: Annotated[str | None, Form()] = None,
    territory_preference: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    if not _required(first_name) or not _required(email):
        raise HTTPException(status_code=400, detail="First name and email are required")
    db.add(
        DriverInterest(
            first_name=first_name.strip(),
            last_name=_optional(last_name),
            email=email.strip().lower(),
            phone=_optional(phone),
            city=_optional(city),
            state=_optional(state),
            vehicle_type=_optional(vehicle_type),
            availability_notes=_optional(availability_notes),
            territory_preference=_optional(territory_preference),
            notes=_optional(notes),
        )
    )
    db.commit()
    return RedirectResponse("/for-drivers?submitted=driver", status_code=303)


@router.post("/contact")
def submit_contact(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    subject: Annotated[str | None, Form()] = None,
):
    if not _required(name) or not _required(email) or not _required(message):
        raise HTTPException(status_code=400, detail="Name, email, and message are required")
    db.add(ContactMessage(name=name.strip(), email=email.strip().lower(), subject=_optional(subject), message=message.strip()))
    db.commit()
    return RedirectResponse("/contact?submitted=contact", status_code=303)


def _public_template(request: Request, template_name: str, path: str, context: dict | None = None):
    title, description = PUBLIC_META[path]
    payload = {
        "request": request,
        "seo_title": title,
        "meta_description": description,
        "og_title": title,
        "og_description": description,
        "canonical_url": str(request.url),
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)


def _temporary_landing_template(request: Request, submitted: str | None = None):
    title = "Farmsource Market | Local Farm Delivery Network"
    description = (
        "Farmsource Market is building a scheduled local delivery network that helps customers discover fresh regional "
        "produce and helps farms reach nearby households."
    )
    return templates.TemplateResponse(
        "temporary_landing.html",
        {
            "request": request,
            "submitted": submitted or request.query_params.get("submitted"),
            "seo_title": title,
            "meta_description": description,
            "canonical_url": str(request.url_for("landing_page")),
        },
    )


def _required(value: str | None) -> bool:
    return bool(value and value.strip())


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
