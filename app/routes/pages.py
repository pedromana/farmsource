from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.models import ContactMessage, DriverInterest, ProducerInterest, WaitlistSignup


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


PUBLIC_META = {
    "/": ("Farmsource | Seattle Local Produce Delivery", "Fresh local produce directly from regional producers through scheduled neighborhood delivery routes in Seattle."),
    "/how-it-works": ("How Farmsource Works | Scheduled Farm Delivery", "How Farmsource curates local produce and delivers scheduled neighborhood routes for the Seattle pilot."),
    "/for-customers": ("For Customers | Farmsource Seattle Produce Waitlist", "Join Farmsource for curated weekly produce, local farm sourcing, and scheduled Seattle-area delivery windows."),
    "/for-producers": ("For Producers | Sell Through Farmsource", "Reach Seattle-area customers with Farmsource customer aggregation, curated offerings, and route-based delivery coordination."),
    "/for-drivers": ("For Drivers | Farmsource Route Delivery", "Predictable neighborhood delivery routes, guaranteed route pay, and community-focused work for the Farmsource Seattle pilot."),
    "/about": ("About Farmsource | Local Food Routes", "Farmsource connects local producers, customers, and route drivers through a simple scheduled delivery model."),
    "/waitlist": ("Join the Farmsource Waitlist | Seattle Pilot", "Join the Farmsource Seattle pilot waitlist as a customer, producer, or driver."),
    "/contact": ("Contact Farmsource | Seattle Pilot", "Contact Farmsource about local produce delivery, producer onboarding, or driver opportunities."),
    "/faq": ("Farmsource FAQ | Seattle Produce Delivery", "Answers about Farmsource delivery windows, participating farms, producers, drivers, and Seattle pilot launch plans."),
}


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    return _public_template(request, "public_home.html", "/")


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
            state=_optional(state) or "WA",
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
            state=_optional(state) or "WA",
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
            state=_optional(state) or "WA",
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
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)


def _required(value: str | None) -> bool:
    return bool(value and value.strip())


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
