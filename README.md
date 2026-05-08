# FarmSource

FarmSource is a local food producer discovery and commerce validation platform. It aggregates publicly available farm and producer listings from configurable source providers, validates whether destination links appear to support real online ordering, stores the results in SQLite, displays qualified producers in a local web dashboard, and exports filtered results to Excel.

The initial provider targets the public WA Food & Farm Finder directory:

https://eatlocalfirst.org/wa-food-farm-finder/

The architecture is intentionally provider-based so future sources such as LocalHarvest, GrownBy, Market Wagon, Barn2Door-powered farms, Harvie-powered farms, Shopify farm stores, WooCommerce farm stores, CSA directories, food hubs, and state directories can be added without rewriting the core application.

## Architecture

```text
farmsource/
  app/
    main.py              FastAPI app, dashboard, admin/source actions
    database.py          SQLite/SQLAlchemy setup
    models.py            Producer, provider, run, error, raw, validation tables
    exporter.py          Filtered XLSX export
    templates/           HTML dashboard and source management pages
    static/              CSS and browser-side dashboard JS
  config/
    providers.yaml       Editable provider/source configuration
  scrapers/
    base.py              Provider interface and normalized listing dataclass
    registry.py          Dynamic provider lookup
    runner.py            Scrape orchestration, validation, persistence
    common/              URL normalization, throttling, validators, classifiers
    providers/
      wa_food_farm_finder/
      localharvest/
      marketwagon/
      grownby/
  data/
    raw/
    processed/
    exports/
  tests/
```

## Provider System

Provider behavior starts in `config/providers.yaml`. Each provider can be enabled or disabled and has editable metadata and crawl settings:

- `base_url`
- `region`
- `source_type`
- `refresh_interval_hours`
- `crawl_delay_seconds`
- `max_pages`
- `max_retries`
- `timeout_seconds`
- `rate_limit_per_minute`
- `allowed_domains`
- `blocked_domains`
- `pagination`
- `validation`

At startup and scraper execution, YAML config is synced into the `source_providers` table. The admin page can toggle providers, update crawl settings, test connections, and trigger rescans.

Provider modules live under `scrapers/providers/<provider_name>/provider.py`. Registered providers are mapped in `scrapers/registry.py`. For a new provider, add the module, expose a provider class that extends `BaseProvider`, and add it to `PROVIDER_CLASSES` or use the default `scrapers.providers.<name>.provider:Provider` convention.

## Qualification Logic

A producer qualifies only when the destination classification is one of:

- `ecommerce_store`
- `csa_signup`
- `subscription_box`
- `farm_platform_store`

The dashboard excludes:

- `informational_page`
- `social_media_page`
- `contact_only`
- `broken_link`
- `unknown`

The classifier automatically excludes social media domains such as Facebook, Instagram, TikTok, LinkedIn, X/Twitter, and YouTube. It detects ecommerce and farm commerce signals including Shopify, Square, Barn2Door, Harvie, GrownBy, Local Line, WooCommerce, GrazeCart, Farmigo, Stripe checkout, PayPal checkout, add to cart, checkout, CSA signup, subscribe, buy now, order online, delivery, and pickup language.

Classification results include:

- destination type
- detected platform
- online ordering confirmation
- confidence score
- classification reason
- pickup and delivery flags

## Database

SQLite is used initially at:

```text
data/farmsource.sqlite3
```

Main tables:

- `source_providers`
- `producers`
- `scrape_runs`
- `scrape_errors`
- `raw_scrape_records`
- `validation_logs`
- `classification_logs`

The `producers` table stores business name, source, listing URL, ecommerce/order URL, region fields, products, classification, platform, confidence, pickup/delivery flags, contact fields, and validation timestamps.

## Setup

Use Python 3.11 or newer.

```powershell
cd C:\Users\pmana\PycharmProjects\farmsource
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Playwright is optional for the first HTTP pass, but useful when a public source renders listings dynamically:

```powershell
playwright install chromium
```

## Run The Scraper

Run all enabled providers:

```powershell
python scrape.py
```

Run one provider:

```powershell
python scrape.py --provider wa_food_farm_finder
```

The scraper uses polite throttling, retry settings, URL normalization, duplicate detection, robots.txt checks, and structured error logging. It does not bypass CAPTCHAs, authentication, access controls, or disallowed robots.txt paths.

## Run The Dashboard

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8010
```

Set `PORT=8000` or another value before running `python app.py` if you want a different local port.

Dashboard features:

- search by farm name
- filter by city, county, state, products, platform, ordering type, source, delivery, and pickup
- sort by confidence score
- open source listings and validated ordering pages
- paginated responsive results
- export filtered results to Excel

Source management:

```text
http://127.0.0.1:8010/admin
```

The admin page supports syncing `providers.yaml`, enabling/disabling providers, editing core crawl settings, testing connections, running rescans, and viewing recent provider health/errors.

## Excel Export

From the dashboard, use Export XLSX to export the current filtered qualified result set.

CLI export:

```powershell
python export_excel.py
python export_excel.py --city Seattle --platform Shopify
```

Exports are written to:

```text
data/exports/
```

Columns:

- `farm_name`
- `city`
- `county`
- `state`
- `products`
- `source_name`
- `source_listing_url`
- `buy_online_url`
- `website_url`
- `destination_type`
- `platform_detected`
- `confidence_score`
- `classification_reason`
- `pickup_available`
- `delivery_available`
- `phone`
- `email_or_contact_url`
- `last_checked_date`

## Add A New Provider

1. Add an entry in `config/providers.yaml`.
2. Create `scrapers/providers/<provider_name>/provider.py`.
3. Implement a class extending `BaseProvider`.
4. Return normalized `ProducerListing` records from `scrape()`.
5. Add the provider to `scrapers/registry.py`, or name the class `Provider` and use the default dynamic convention.
6. Run `python scrape.py --provider <provider_name>`.

The validation and classification pipeline is shared, so each provider only needs to collect listing metadata and candidate ecommerce/order URLs.

## Scaling Recommendations

Near-term improvements:

- move long-running scrapes into a background worker such as RQ, Celery, or Dramatiq
- add scheduled revalidation jobs
- add provider-specific parsers with fixture tests
- add full-text search indexes
- expose provider config editing directly back to YAML or move all source config into the database

Larger-scale improvements:

- migrate from SQLite to PostgreSQL
- add crawl frontier/resume queues
- store raw HTML in object storage
- split validation into independent URL jobs
- add platform-specific validators for Shopify, WooCommerce, Barn2Door, Harvie, GrownBy, and Market Wagon
- add audit review workflows for low-confidence classifications
