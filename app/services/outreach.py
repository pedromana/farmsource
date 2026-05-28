from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass
from io import StringIO
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ImportRun, Producer, ProducerOutreachCandidate, Source
from app.services.csv_importer import import_producers_from_csv


OUTREACH_STATUSES = ("prospect", "researching", "contacted", "interested", "not_a_fit", "onboarding", "active")
RESEARCH_STATUSES = ("not_started", "needs_research", "researching", "found_contact", "no_contact_found", "verified")
COMPLETED_RESEARCH_STATUSES = ("found_contact", "no_contact_found", "verified")
LOCKED_RESEARCH_STATUSES = ("found_contact", "verified")
RESEARCH_BATCH_SIZE = 10
SEARCH_RESULT_LIMIT = 10
PAGE_FETCH_LIMIT = 5
REQUEST_TIMEOUT_SECONDS = 8
USER_AGENT = "Farmsource local outreach research/1.0"

FIELD_ALIASES = {
    "business_name": ("business_name", "business", "company", "organization", "org_name", "producer_name", "farm_name", "farm", "name"),
    "producer_name": ("producer_name", "farm_name", "farm", "name", "business_name", "business", "company"),
    "business_type": ("business_type", "producer_type", "type", "category"),
    "address": ("principal_office_address", "address", "street_address", "mailing_address", "office_address"),
    "city": ("city", "town"),
    "state": ("state", "province"),
    "zip_code": ("zip_code", "zip", "postal_code", "postcode"),
    "ubi": ("ubi", "ubi#", "business_id", "license_number", "registration_number"),
    "registered_agent": ("registered_agent_name", "registered_agent", "agent_name", "contact_name"),
    "status": ("status", "business_status"),
    "website_url": ("website_url", "website", "site", "url", "business_url"),
    "contact_email": ("contact_email", "email", "e-mail"),
    "contact_phone": ("contact_phone", "phone", "telephone", "mobile"),
    "products": ("products", "product", "offerings", "produce", "items"),
    "notes": ("notes", "description", "summary", "details"),
}

REGION_PROFILES = {
    "seattle": {
        "label": "Seattle / Western Washington",
        "state": "WA",
        "cities": {
            "SNOHOMISH": 100,
            "WOODINVILLE": 100,
            "CARNATION": 100,
            "DUVALL": 100,
            "MONROE": 96,
            "ARLINGTON": 94,
            "STANWOOD": 94,
            "MOUNT VERNON": 94,
            "BOW": 92,
            "LA CONNER": 92,
            "CONWAY": 92,
            "BURLINGTON": 90,
            "SEDRO WOOLLEY": 90,
            "BELLINGHAM": 90,
            "LYNDEN": 88,
            "EVERSON": 88,
            "EVERETT": 88,
            "FERNDALE": 86,
            "MARYSVILLE": 86,
            "BOTHELL": 86,
            "REDMOND": 84,
            "BELLEVUE": 82,
            "ISSAQUAH": 82,
            "NORTH BEND": 82,
            "ENUMCLAW": 82,
            "SEATTLE": 78,
            "KENT": 76,
            "AUBURN": 76,
            "TACOMA": 74,
            "OLYMPIA": 72,
            "PUYALLUP": 72,
            "SUMNER": 72,
        },
    },
    "washington": {
        "label": "All Washington",
        "state": "WA",
        "cities": {},
    },
}

STRONG_INCLUDE = (
    "organic",
    "produce",
    "vegetable",
    "veggie",
    "berry",
    "berries",
    "orchard",
    "fruit",
    "harvest",
    "market",
    "dairy",
    "creamery",
    "pasture",
    "apiary",
    "honey",
    "greenhouse",
    "nursery",
    "lavender",
    "flower",
    "floral",
    "farmstand",
    "farm stand",
    "roots",
    "acres",
    "family farm",
    "fresh",
    "garden",
    "csa",
)

EXCLUDE_KEYWORDS = (
    "association",
    "homeowners",
    "condominium",
    "condo",
    "estate",
    "estates",
    "hoa",
    "insurance",
    "trucking",
    "transport",
    "logistics",
    "realty",
    "real estate",
    "property",
    "properties",
    "holdings",
    "capital",
    "investment",
    "investments",
    "land company",
    "solar",
    "wind farm",
    "data farm",
    "server farm",
    "game farm park",
    "apartments",
    "ministries",
    "church",
    "foundation",
    "political",
    "consulting",
    "marketing",
    "equestrian",
    "horse",
    "horses",
    "events",
    "wedding",
    "venue",
    "tree farm",
    "christmas trees",
    "cannabis",
    "marijuana",
    "hemp",
    "cbd",
    "preschool",
    "school",
    "children",
    "childrens",
    "dessert",
    "bakery",
    "baked",
    "hobby farm",
    "vacation",
    "airbnb",
    "rental",
    "rentals",
)

LOWER_PRIORITY = ("nonprofit", "flower", "floral", "lavender", "nursery", "ranch", "livestock")


@dataclass(frozen=True)
class OutreachImportSummary:
    source_id: int
    import_run_id: int
    imported_rows: int
    candidate_count: int
    top_count: int
    filtered_out_count: int


def normalize_outreach_csv(
    db: Session,
    *,
    content: bytes,
    filename: str,
    source_name: str,
    region: str,
    active_status_only: bool = True,
    state_filter: str | None = None,
    clear_existing_region: bool = False,
) -> OutreachImportSummary:
    source = _ensure_source(db, source_name, filename, region)
    normalized_content, eligible_rows = _normalize_csv_content(content, active_status_only, state_filter)
    import_summary = import_producers_from_csv(db, source.id, filename, normalized_content)

    if clear_existing_region:
        db.execute(delete(ProducerOutreachCandidate).where(ProducerOutreachCandidate.region == region))
        db.commit()

    producers = db.scalars(select(Producer).where(Producer.source_id == source.id)).all()
    rows = []
    filtered_out = 0
    for producer in producers:
        score, reason = score_producer(producer, region)
        if not _candidate_is_eligible(producer, region, score, reason):
            filtered_out += 1
            continue
        rows.append((score, reason, producer))

    rows.sort(key=lambda item: (-item[0], (item[2].city or ""), item[2].producer_name))
    existing_ids = set(
        db.scalars(select(ProducerOutreachCandidate.producer_id).where(ProducerOutreachCandidate.producer_id.is_not(None)))
    )
    candidate_count = 0
    for rank, (score, reason, producer) in enumerate(rows, start=1):
        if producer.id in existing_ids:
            continue
        db.add(_candidate_from_producer(producer, source.id, import_summary.import_run_id, region, rank, score, reason))
        candidate_count += 1
    db.commit()
    return OutreachImportSummary(
        source_id=source.id,
        import_run_id=import_summary.import_run_id,
        imported_rows=import_summary.imported_rows,
        candidate_count=candidate_count,
        top_count=min(candidate_count, 100),
        filtered_out_count=max(eligible_rows - candidate_count, filtered_out),
    )


def score_producer(producer: Producer, region: str) -> tuple[int, str]:
    profile = REGION_PROFILES.get(region, REGION_PROFILES["seattle"])
    target_state = str(profile.get("state") or "").upper()
    city_scores: dict[str, int] = profile.get("cities", {})  # type: ignore[assignment]
    city = (producer.city or "").upper()
    state = (producer.state or "").upper()
    haystack = f"{producer.producer_name or ''} {producer.business_name or ''} {producer.producer_type or ''} {producer.products or ''} {producer.notes or ''}".lower()
    score = city_scores.get(city, 70 if state == target_state else 20)
    reasons = []

    if city in city_scores:
        reasons.append(f"target region city: {city}")
    elif state == target_state:
        reasons.append(f"target state: {state}")
    else:
        reasons.append(f"outside target state: {state or 'blank'}")

    include_matches = [word for word in STRONG_INCLUDE if word in haystack]
    if include_matches:
        score += 8 + min((len(include_matches) - 1) * 2, 10)
        reasons.append("producer keyword: " + ", ".join(include_matches[:3]))

    excluded = [word for word in EXCLUDE_KEYWORDS if word in haystack]
    if excluded:
        score -= 100
        reasons.append("excluded/low-fit keyword: " + ", ".join(excluded[:3]))

    lower = [word for word in LOWER_PRIORITY if word in haystack]
    if lower:
        score -= 8
        reasons.append("secondary category: " + ", ".join(lower[:2]))

    if "limited liability company" in (producer.producer_type or "").lower() or "profit corporation" in (producer.producer_type or "").lower():
        score += 3
    return score, "; ".join(reasons)


def _normalize_csv_content(content: bytes, active_status_only: bool, state_filter: str | None) -> tuple[bytes, int]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        return content, 0
    header_map = _build_header_map(reader.fieldnames)
    output = StringIO()
    fieldnames = [
        "producer_name",
        "business_name",
        "city",
        "state",
        "zip_code",
        "producer_type",
        "website_url",
        "contact_email",
        "contact_phone",
        "products",
        "notes",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    eligible_rows = 0
    for row in reader:
        mapped = _map_row(row, header_map)
        if active_status_only and mapped.get("status") and mapped["status"].strip().lower() != "active":
            continue
        city, state, zip_code = _address_parts(mapped.get("address"))
        mapped["city"] = mapped.get("city") or city
        mapped["state"] = mapped.get("state") or state
        mapped["zip_code"] = mapped.get("zip_code") or zip_code
        if state_filter and (mapped.get("state") or "").upper() != state_filter.upper():
            continue
        name = (mapped.get("producer_name") or mapped.get("business_name") or "").strip().strip('"')
        if not name:
            continue
        eligible_rows += 1
        notes = _notes(row, mapped)
        writer.writerow(
            {
                "producer_name": name,
                "business_name": (mapped.get("business_name") or name).strip().strip('"'),
                "city": mapped.get("city") or "",
                "state": mapped.get("state") or "",
                "zip_code": mapped.get("zip_code") or "",
                "producer_type": mapped.get("business_type") or "",
                "website_url": mapped.get("website_url") or "",
                "contact_email": mapped.get("contact_email") or "",
                "contact_phone": mapped.get("contact_phone") or "",
                "products": mapped.get("products") or "",
                "notes": notes,
            }
        )
    return output.getvalue().encode("utf-8"), eligible_rows


def _candidate_is_eligible(producer: Producer, region: str, score: int, reason: str) -> bool:
    profile = REGION_PROFILES.get(region, REGION_PROFILES["seattle"])
    target_state = str(profile.get("state") or "").upper()
    city_scores: dict[str, int] = profile.get("cities", {})  # type: ignore[assignment]
    city = (producer.city or "").upper()
    state = (producer.state or "").upper()
    if state != target_state:
        return False
    if "excluded/low-fit" in reason and score < 70:
        return False
    if city_scores and city not in city_scores and score < 85:
        return False
    return score >= 55


def _candidate_from_producer(
    producer: Producer,
    source_id: int,
    import_run_id: int,
    region: str,
    rank: int,
    score: int,
    reason: str,
) -> ProducerOutreachCandidate:
    ubi = _extract_note("WA UBI", producer.notes)
    address = _extract_note("Principal office address", producer.notes)
    return ProducerOutreachCandidate(
        source_id=source_id,
        import_run_id=import_run_id,
        producer_id=producer.id,
        region=region,
        priority_rank=rank,
        priority_score=score,
        producer_name=producer.producer_name,
        business_name=producer.business_name,
        city=producer.city,
        state=producer.state,
        zip_code=producer.zip_code,
        producer_type=producer.producer_type,
        ubi=ubi,
        registered_agent=_extract_note("Registered agent", producer.notes),
        principal_office_address=address,
        website_url=producer.website_url,
        contact_email=producer.contact_email,
        contact_phone=producer.contact_phone,
        instagram_url=producer.instagram_url,
        facebook_url=producer.facebook_url,
        outreach_status="prospect",
        research_status=(
            "found_contact"
            if producer.contact_email
            or producer.website_url
            or producer.contact_phone
            or producer.instagram_url
            or producer.facebook_url
            else "needs_research"
        ),
        search_url=build_research_url(producer.producer_name, producer.city, producer.state),
        priority_reason=reason,
        next_step="Research website/email, then send first outreach message",
        notes=producer.notes,
    )


def build_research_url(producer_name: str, city: str | None, state: str | None) -> str:
    query = " ".join(part for part in [producer_name, city, state, "farm contact email"] if part)
    return f"https://www.google.com/search?q={quote_plus(query)}"


def request_candidate_research(candidate: ProducerOutreachCandidate) -> None:
    if candidate.research_status in LOCKED_RESEARCH_STATUSES:
        candidate.next_step = candidate.next_step or "Research already completed. Review notes before outreach."
        return
    candidate.research_status = "researching"
    candidate.outreach_status = "researching"
    candidate.search_url = candidate.search_url or build_research_url(candidate.producer_name, candidate.city, candidate.state)
    candidate.next_step = "Research requested. Find website, email, phone, contact form, and farm product fit."


def research_candidate_now(candidate: ProducerOutreachCandidate) -> ProducerOutreachCandidate:
    if candidate.research_status in LOCKED_RESEARCH_STATUSES:
        return candidate

    candidate.search_url = candidate.search_url or build_research_url(candidate.producer_name, candidate.city, candidate.state)
    results = _candidate_search_results(candidate)
    selected_results = _best_research_results(results, candidate)
    page_texts = []
    source_urls = []

    for result in selected_results[:PAGE_FETCH_LIMIT]:
        page_url = result.get("url")
        if not page_url:
            continue
        source_urls.append(page_url)
        if not candidate.website_url and not _directory_result_url(page_url):
            candidate.website_url = page_url
        page_text = _fetch_page_text(page_url)
        if page_text:
            page_texts.append(page_text)

    search_text = " ".join(result.get("text", "") for result in selected_results or results)
    combined_text = f"{search_text} {' '.join(page_texts)}"
    email = _extract_email(combined_text)
    phone = _extract_phone(combined_text)
    instagram_url = _extract_social_url(combined_text, "instagram")
    facebook_url = _extract_social_url(combined_text, "facebook")
    if email:
        candidate.contact_email = candidate.contact_email or email
    if phone:
        candidate.contact_phone = candidate.contact_phone or phone
    if instagram_url:
        candidate.instagram_url = candidate.instagram_url or instagram_url
    if facebook_url:
        candidate.facebook_url = candidate.facebook_url or facebook_url

    if not candidate.website_url and selected_results:
        contact_form_url = _first_contact_form_url(selected_results)
        if contact_form_url:
            candidate.website_url = contact_form_url

    found_any = bool(
        candidate.website_url
        or candidate.contact_email
        or candidate.contact_phone
        or candidate.instagram_url
        or candidate.facebook_url
    )
    candidate.research_status = "found_contact" if found_any else "no_contact_found"
    if found_any and candidate.outreach_status == "researching":
        candidate.outreach_status = "prospect"
    candidate.next_step = _research_next_step(candidate, found_any)
    candidate.notes = _append_research_note(candidate.notes, _research_note(candidate, selected_results, found_any, source_urls))
    return candidate


def _candidate_search_results(candidate: ProducerOutreachCandidate) -> list[dict[str, str]]:
    farm_name = _friendly_farm_name(candidate.producer_name)
    location = " ".join(part for part in [candidate.city, candidate.state] if part)
    queries = [
        " ".join(part for part in [candidate.producer_name, location, "farm contact email phone"] if part),
        " ".join(part for part in [candidate.producer_name, location, "Instagram Facebook"] if part),
        " ".join(part for part in [farm_name, location, "LocalHarvest"] if part),
        " ".join(part for part in [farm_name, location, "website"] if part),
        " ".join(part for part in [farm_name, location, "Chamber"] if part),
        " ".join(part for part in [farm_name, location, "MapQuest phone"] if part),
    ]
    results: list[dict[str, str]] = []
    for query in dict.fromkeys(queries):
        query_results = _search_web(query)
        results.extend(query_results)
        if len(_best_research_results(_dedupe_results(results), candidate)) >= 3:
            break
    return _dedupe_results(results)[: SEARCH_RESULT_LIMIT * 2]


def research_next_candidates(db: Session, region: str, limit: int = RESEARCH_BATCH_SIZE) -> list[ProducerOutreachCandidate]:
    candidates = db.scalars(
        select(ProducerOutreachCandidate)
        .where(
            ProducerOutreachCandidate.region == region,
            ProducerOutreachCandidate.research_status.not_in(COMPLETED_RESEARCH_STATUSES),
        )
        .order_by(ProducerOutreachCandidate.priority_rank, ProducerOutreachCandidate.priority_score.desc())
        .limit(limit)
    ).all()
    for candidate in candidates:
        research_candidate_now(candidate)
        if candidate.producer_id:
            producer = db.get(Producer, candidate.producer_id)
            if producer:
                producer.website_url = candidate.website_url or producer.website_url
                producer.contact_email = candidate.contact_email or producer.contact_email
                producer.contact_phone = candidate.contact_phone or producer.contact_phone
                producer.instagram_url = candidate.instagram_url or producer.instagram_url
                producer.facebook_url = candidate.facebook_url or producer.facebook_url
                producer.notes = candidate.notes or producer.notes
    return candidates


def generate_outreach_email(candidate: ProducerOutreachCandidate) -> dict[str, str]:
    farm_name = _friendly_farm_name(candidate.producer_name)
    region = ", ".join(part for part in (candidate.city, candidate.state) if part)
    subject = "Local delivery support for your farm"
    contact_name = _researched_contact_name(candidate.notes)
    greeting = f"Hello {contact_name.split()[0].title()}," if contact_name else "Hello,"
    body = f"""{greeting}

My name is Pedro, and I am building Farmsource, a local farm-to-customer delivery service for fresh food producers.

I came across {farm_name}{f" in {region}" if region else ""} while researching local farms that may benefit from a simpler delivery option.

The idea is straightforward: Farmsource would help farms reach more local customers by adding a scheduled delivery channel without asking the farm to run its own delivery operation.

For farms that do not currently offer delivery, this could help:

- make products accessible to customers who cannot make it to markets or farm pickup
- increase local awareness beyond the existing customer base
- batch orders into predictable delivery windows instead of one-off trips
- keep the first workflow simple while we validate demand

Would you be open to a 15-minute conversation so I can explain how we can help your business and understand whether a scheduled delivery model could be useful for your farm?

Thank you,

Pedro
Farmsource
farmsourcemarket.com"""
    mailto = f"mailto:{candidate.contact_email}?subject={quote_plus(subject)}&body={quote_plus(body)}"
    gmail_compose = (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&to={quote_plus(candidate.contact_email or '')}"
        f"&su={quote_plus(subject)}"
        f"&body={quote_plus(body)}"
    )
    return {"subject": subject, "body": body, "mailto": mailto, "gmail_compose": gmail_compose}


def _friendly_farm_name(name: str) -> str:
    cleaned = re.sub(r"\b(LLC|L\.L\.C\.|INC\.?|CORP\.?|LIMITED LIABILITY COMPANY)\b", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned.title() if cleaned.isupper() else cleaned


def _search_web(query: str) -> list[dict[str, str]]:
    results = []
    url = "https://duckduckgo.com/html/"
    try:
        response = httpx.get(
            url,
            params={"q": query},
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        response = None
    if response is not None:
        results.extend(_parse_duckduckgo_results(response.text))

    if len(results) < 4:
        try:
            bing = httpx.get(
                "https://www.bing.com/search",
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            bing.raise_for_status()
            results.extend(_parse_bing_results(bing.text))
        except httpx.HTTPError:
            pass
    return _dedupe_results(results)[:SEARCH_RESULT_LIMIT]


def _parse_duckduckgo_results(markup: str) -> list[dict[str, str]]:
    results = []
    for match in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', markup, re.IGNORECASE | re.DOTALL):
        raw_url, raw_title = match.groups()
        url = _clean_result_url(html.unescape(raw_url))
        if not url:
            continue
        title = _strip_tags(raw_title)
        tail = markup[match.end() : match.end() + 1800]
        snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', tail, re.IGNORECASE | re.DOTALL)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        results.append({"url": url, "title": title, "snippet": snippet, "text": f"{title} {snippet}"})
        if len(results) >= SEARCH_RESULT_LIMIT:
            break
    return results


def _parse_bing_results(markup: str) -> list[dict[str, str]]:
    results = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', markup, flags=re.IGNORECASE | re.DOTALL)
    for block in blocks:
        link_match = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL)
        if not link_match:
            continue
        url = _clean_result_url(html.unescape(link_match.group(1)))
        if not url.startswith("http"):
            continue
        title = _strip_tags(link_match.group(2))
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        results.append({"url": url, "title": title, "snippet": snippet, "text": f"{title} {snippet}"})
        if len(results) >= SEARCH_RESULT_LIMIT:
            break
    return results


def _best_research_results(results: list[dict[str, str]], candidate: ProducerOutreachCandidate) -> list[dict[str, str]]:
    if not results:
        return []
    candidate_tokens = _name_tokens(candidate.producer_name)
    city = (candidate.city or "").lower()
    state = (candidate.state or "").lower()
    scored = []
    for result in results:
        haystack = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}".lower()
        token_matches = sum(1 for token in candidate_tokens if token in haystack)
        score = token_matches * 4
        exact_name = _name_signature(candidate.producer_name) in _name_signature(haystack)
        if city and city in haystack:
            score += 5
        if state and f" {state} " in f" {haystack} ":
            score += 2
        if any(word in haystack for word in ("farm", "produce", "organic", "csa", "vegetable", "berry", "orchard")):
            score += 2
        if _directory_result_url(result.get("url", "")):
            score -= 2
        if _generic_result_url(result.get("url", "")):
            score -= 8
        if any(word in haystack for word in ("contact", "email", "phone", "website", "localharvest", "eatlocalfirst")):
            score += 2
        if "instagram.com" in haystack or "facebook.com" in haystack:
            score += 3
        has_location_match = bool(city and city in haystack) or bool(state and f" {state} " in f" {haystack} ")
        if (
            token_matches > 0
            and score >= 8
            and (exact_name or has_location_match or token_matches >= 2)
            and _identity_match_result(result, candidate)
        ):
            scored.append((score, result))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [result for score, result in scored if score >= 4]
    selected.sort(key=lambda result: _result_priority(result.get("url", ""), candidate))
    return selected[:PAGE_FETCH_LIMIT]


def _fetch_page_text(url: str) -> str:
    texts = []
    urls = [url]
    try:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        base_text = response.text
    except httpx.HTTPError:
        return ""
    texts.append(f"{_strip_tags(base_text)} {' '.join(_page_href_urls(base_text))}")
    for link in _contact_links(url, base_text)[: PAGE_FETCH_LIMIT - 1]:
        try:
            linked = httpx.get(link, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
            linked.raise_for_status()
            texts.append(f"{_strip_tags(linked.text)} {' '.join(_page_href_urls(linked.text))}")
        except httpx.HTTPError:
            continue
    return " ".join(texts)


def _contact_links(base_url: str, markup: str) -> list[str]:
    links = []
    parsed_base = urlparse(base_url)
    for href in re.findall(r'href=["\']([^"\']+)["\']', markup, flags=re.IGNORECASE):
        href = html.unescape(href)
        if href.startswith("mailto:"):
            links.append(href)
            continue
        lower = href.lower()
        if "contact" not in lower and "about" not in lower and "instagram.com" not in lower and "facebook.com" not in lower:
            continue
        if href.startswith("/"):
            links.append(f"{parsed_base.scheme}://{parsed_base.netloc}{href}")
        elif href.startswith("http") and urlparse(href).netloc == parsed_base.netloc:
            links.append(href)
    deduped = []
    for link in links:
        if link not in deduped:
            deduped.append(link)
    return deduped


def _page_href_urls(markup: str) -> list[str]:
    urls = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', markup, flags=re.IGNORECASE):
        href = html.unescape(href)
        if href.startswith("http") and ("instagram.com" in href.lower() or "facebook.com" in href.lower()):
            urls.append(href)
    return list(dict.fromkeys(urls))


def _clean_result_url(url: str) -> str | None:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.query:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    if "bing.com" in parsed.netloc and parsed.path.startswith("/ck/"):
        target = parse_qs(parsed.query).get("u")
        if target:
            decoded = _decode_bing_url(target[0])
            if decoded:
                return decoded
    if url.startswith("http"):
        return url
    return None


def _directory_result_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    excluded_hosts = (
        "bizprofile.net",
        "bizapedia.com",
        "b2bhint.com",
        "opencorporates.com",
        "dnb.com",
        "zillow.com",
        "realtor.com",
        "corporationwiki.com",
        "company-information.service.gov.uk",
        "opengovwa.com",
        "city-data.com",
        "washingtoncompany.net",
        "washington-company.com",
        "buzzfile.com",
    )
    return any(excluded in host for excluded in excluded_hosts)


def _generic_result_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    generic_hosts = (
        "wikipedia.org",
        "britannica.com",
        "nationalgeographic.com",
        "animalcorner.org",
        "ciwf.com",
        "farmsanctuary.org",
        "nfm.com",
    )
    return any(excluded in host for excluded in generic_hosts)


def _result_priority(url: str, candidate: ProducerOutreachCandidate) -> tuple[int, str]:
    host = urlparse(url).netloc.lower()
    name_tokens = _name_tokens(candidate.producer_name)
    host_matches = sum(1 for token in name_tokens if token in host)
    if _directory_result_url(url):
        return (4, host)
    if host_matches >= min(2, len(name_tokens)):
        return (0, host)
    if "localharvest.org" in host or "eatlocalfirst.org" in host:
        return (2, host)
    if "chamber" in host or "mapquest.com" in host or "snovalleydirectory.com" in host:
        return (3, host)
    if "facebook.com" in host or "instagram.com" in host:
        return (4, host)
    return (1, host)


def _decode_bing_url(value: str) -> str | None:
    import base64

    payload = value[2:] if value.startswith("a1") else value
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8", errors="ignore")
    except ValueError:
        return None
    return decoded if decoded.startswith("http") else None


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for result in results:
        url = result.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(result)
    return deduped


def _first_contact_form_url(results: list[dict[str, str]]) -> str | None:
    for result in results:
        url = result.get("url", "")
        haystack = f"{result.get('title', '')} {result.get('snippet', '')} {url}".lower()
        if _directory_result_url(url):
            continue
        if any(word in haystack for word in ("contact", "website", "localharvest", "eatlocalfirst", "facebook.com", "instagram.com")):
            return url
    return None


def _strip_tags(value: str) -> str:
    value = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _extract_email(text: str) -> str | None:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.IGNORECASE)
    if not match:
        return None
    email = match.group(0).strip(".,;:()[]{}<>")
    if any(skip in email.lower() for skip in ("example.com", "domain.com", "email.com")):
        return None
    return email


def _extract_phone(text: str) -> str | None:
    washington_area_codes = {"206", "253", "360", "425", "509", "564"}
    phones = []
    for match in re.finditer(r"(?:\+1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}", text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            continue
        phone = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        phones.append((digits[:3] in washington_area_codes, phone))
    for is_washington, phone in phones:
        if is_washington:
            return phone
    return None


def _extract_social_url(text: str, platform: str) -> str | None:
    if platform == "instagram":
        blocked = {"explore", "p", "reel", "stories", "accounts"}
    elif platform == "facebook":
        blocked = {"share", "sharer", "events", "groups", "login", "pages", "bizapedia"}
    else:
        return None

    pattern = rf"https?://(?:www\.)?{platform}\.com/[^\s<>'\")\]]+"
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        url = html.unescape(match.group(0)).strip(".,;:()[]{}<>\"'")
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.strip("/").split("/") if part]
        if not path_parts or path_parts[0].lower() in blocked:
            continue
        if platform == "instagram":
            return f"https://www.instagram.com/{path_parts[0]}/"
        if path_parts[0].lower() == "people" and len(path_parts) >= 3:
            return f"https://www.facebook.com/people/{path_parts[1]}/{path_parts[2]}/"
        if path_parts[0].lower() == "p" and len(path_parts) >= 2:
            return f"https://www.facebook.com/p/{path_parts[1]}/"
        if path_parts[0].lower() == "profile.php" and parsed.query:
            return f"https://www.facebook.com/profile.php?{parsed.query}"
        return f"https://www.facebook.com/{path_parts[0]}/"
    return None


def _name_tokens(name: str) -> list[str]:
    ignored = {"llc", "inc", "farm", "farms", "family", "the", "and", "l", "c"}
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    return [token for token in tokens if len(token) > 2 and token not in ignored]


def _name_signature(name: str) -> str:
    return " ".join(_name_tokens(name))


def _identity_match_result(result: dict[str, str], candidate: ProducerOutreachCandidate) -> bool:
    title_url = f"{result.get('title', '')} {result.get('url', '')}".lower()
    title_url_signature = _name_signature(title_url)
    candidate_signature = _name_signature(candidate.producer_name)
    if candidate_signature and candidate_signature in title_url_signature:
        return True
    tokens = _name_tokens(candidate.producer_name)
    matches = sum(1 for token in tokens if token in title_url)
    return matches >= min(2, len(tokens))


def _research_next_step(candidate: ProducerOutreachCandidate, found_any: bool) -> str:
    if candidate.contact_email:
        return "Review the researched details, then send the outreach email draft."
    if candidate.contact_phone:
        return "Call first and ask for the best email for a Farmsource delivery conversation."
    if candidate.instagram_url or candidate.facebook_url:
        return "Review social profile and decide whether to contact or follow manually."
    if candidate.website_url:
        return "Review website/contact form and decide whether to contact manually."
    if found_any:
        return "Review researched details before outreach."
    return "No reliable public contact found. Skip first outreach batch unless contact is found manually."


def _research_note(
    candidate: ProducerOutreachCandidate,
    results: list[dict[str, str]],
    found_any: bool,
    source_urls: list[str],
) -> str:
    if results and found_any:
        urls = source_urls or [result.get("url", "") for result in results if result.get("url")]
        details = [f"Local auto-research checked {', '.join(urls[:3])}"]
        if candidate.contact_email:
            details.append(f"email {candidate.contact_email}")
        if candidate.contact_phone:
            details.append(f"phone {candidate.contact_phone}")
        if candidate.instagram_url:
            details.append(f"Instagram {candidate.instagram_url}")
        if candidate.facebook_url:
            details.append(f"Facebook {candidate.facebook_url}")
        if candidate.website_url and not candidate.contact_email and not candidate.contact_phone:
            details.append("website/contact page found")
        return "; ".join(details) + "."
    if results:
        urls = [result.get("url", "") for result in results if result.get("url")]
        return f"Local auto-research checked {', '.join(urls[:3])} but did not find a reliable website, email, or phone."
    return "Local auto-research did not find a reliable farm website, email, phone, or product listing."


def _append_research_note(existing: str | None, note: str) -> str:
    prefix = "Research 2026-05-19"
    entry = f"{prefix}: {note}"
    return f"{existing}; {entry}" if existing else entry


def _researched_contact_name(notes: str | None) -> str | None:
    if not notes:
        return None
    for label in ("Contact name", "Research contact name", "Website contact name"):
        value = _extract_note(label, notes)
        if value:
            return value
    return None


def _ensure_source(db: Session, source_name: str, filename: str, region: str) -> Source:
    name = source_name.strip() or filename
    source = db.scalar(select(Source).where(Source.source_name == name))
    if source:
        return source
    source = Source(
        source_name=name,
        source_type="producer_outreach_csv",
        source_url=filename,
        region=region,
        state=str(REGION_PROFILES.get(region, {}).get("state") or ""),
        notes="CSV uploaded through producer outreach normalization workflow.",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    normalized_headers = {_normalize_header(header): header for header in fieldnames}
    header_map = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                header_map[field] = normalized_headers[alias]
                break
    return header_map


def _map_row(row: dict[str, str], header_map: dict[str, str]) -> dict[str, str]:
    mapped = {}
    for field in FIELD_ALIASES:
        header = header_map.get(field)
        mapped[field] = (row.get(header, "") if header else "").strip()
    return mapped


def _address_parts(address: str | None) -> tuple[str | None, str | None, str | None]:
    if not address:
        return None, None, None
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 4:
        return parts[-4], parts[-3], parts[-2]
    return None, None, None


def _notes(row: dict[str, str], mapped: dict[str, str]) -> str:
    note_parts = []
    if mapped.get("ubi"):
        note_parts.append(f"WA UBI: {mapped['ubi']}")
    if mapped.get("registered_agent"):
        note_parts.append(f"Registered agent: {mapped['registered_agent']}")
    if mapped.get("status"):
        note_parts.append(f"Registry status: {mapped['status']}")
    if mapped.get("address"):
        note_parts.append(f"Principal office address: {mapped['address']}")
    if mapped.get("notes"):
        note_parts.append(mapped["notes"])
    note_parts.append(f"Raw row: {json.dumps(row)}")
    return "; ".join(part for part in note_parts if part)


def _extract_note(label: str, notes: str | None) -> str | None:
    if not notes:
        return None
    match = re.search(rf"{re.escape(label)}: ([^;]+)", notes)
    return match.group(1).strip() if match else None


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_").replace("#", "")
