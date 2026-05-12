# Farmsource

Farmsource is a v1 foundation for a local farm-to-consumer marketplace. The pilot is aimed at the Seattle region and is designed around scheduled delivery routes, not instant delivery.

This repository is intentionally small: it provides the FastAPI app, environment-based configuration, SQLite database setup, static files, basic page shells, Docker support, and deployment notes.

## What is included

- Customer-facing shell at `/customer`
- Admin dashboard shell at `/admin`
- Generic source management at `/admin/sources`
- Producer CSV import at `/admin/imports`
- Producer review, filtering, qualification, editing, and Excel export at `/admin/producers`
- Product catalog management at `/admin/products`
- Category management at `/admin/categories`
- Delivery-window availability at `/admin/availability`
- Customer catalog at `/customer/catalog`
- Driver mobile-friendly shell at `/driver`
- Landing page at `/`
- Health check at `/health`
- SQLAlchemy setup using `DATABASE_URL`
- SQLite local default with an easy path to PostgreSQL later
- PWA-friendly static structure with a manifest and service worker placeholder
- Dockerfile and `docker-compose.yml`
- pandas and openpyxl dependencies for later Excel export work
- Rule-based ordering readiness classification for ecommerce, CSA, platform stores, contact-only pages, social media, and unknown destinations
- Curated v1 product catalog with simple delivery-window inventory

## Project structure

```text
farmsource/
  app/
    main.py
    config.py
    database.py
    models.py
    schemas.py
    routes/
    services/
    templates/
    static/
  admin/
  customer/
  driver/
  data/
    imports/
    exports/
  tests/
  requirements.txt
  Dockerfile
  docker-compose.yml
  .env.example
  README.md
  .gitignore
```

## Local setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Start the development server:

```bash
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/admin`
- `http://127.0.0.1:8000/customer`
- `http://127.0.0.1:8000/driver`
- `http://127.0.0.1:8000/health`

## Database initialization

The app creates the initial SQLAlchemy tables on startup. The default local database is:

```env
DATABASE_URL=sqlite:///./data/farmsource.db
```

To initialize manually, run:

```bash
python -c "from app.database import init_db; init_db()"
```

For PostgreSQL later, install an appropriate driver such as `psycopg` and set:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/farmsource
```

Alembic migrations can be added when the data model stabilizes beyond the v1 foundation.

## Producer source database

Phase 2 adds generic tables for:

- `sources`: CSV files, farm directories, marketplaces, CSA directories, direct farm sites, or future connectors
- `producers`: normalized producer records with URLs, location, products, contact fields, destination classification, and qualification status
- `import_runs`: CSV import summaries
- `import_error_rows`: skipped or errored CSV row details

The system is source-agnostic. It is not tied to Washington Food & Farm Finder and can later support directories or marketplaces such as LocalHarvest, GrownBy, Market Wagon, Barn2Door-powered farms, Harvie-powered farms, direct farm websites, and manual CSV exports.

## CSV imports

Open `http://127.0.0.1:8000/admin/imports` and upload a CSV. The importer maps common column names automatically, including:

- producer names: `producer_name`, `farm_name`, `farm`, `name`, `vendor`, `supplier`
- URLs: `website`, `website_url`, `shop_url`, `store_url`, `order_url`, `listing_url`
- location: `city`, `county`, `state`, `zip`, `postal_code`
- products: `products`, `offerings`, `categories`, `produce`
- fulfillment: `delivery`, `pickup`
- contact: `email`, `phone`

Duplicates are skipped using `website_url`, `online_order_url`, `source_listing_url`, or `producer_name + city + state`.

## Classification

Imported and edited producers are classified with rule-based logic. Destination types include:

- `ecommerce_store`
- `csa_signup`
- `subscription_box`
- `farm_platform_store`
- `informational_page`
- `contact_only`
- `social_media_page`
- `broken_link`
- `unknown`

Social media destinations are not qualified. Platform indicators currently include Shopify, Square, Barn2Door, Harvie, GrownBy, Local Line, WooCommerce, GrazeCart, Farmigo, Stripe, and PayPal.

## Product Catalog

Phase 3 adds a curated product catalog foundation for weekly produce offerings, seasonal boxes, selected farm products, and add-ons. It is intentionally not designed as a large grocery SKU system.

Catalog tables:

- `product_categories`: curated categories such as Produce Boxes, Vegetables, Fruits, Seasonal Bundles, Herbs, Add-ons, Dairy, Eggs, Bakery, and Pantry
- `products`: products connected to imported producers and optional categories
- `product_availability`: simple delivery-window availability with `available_quantity`, `reserved_quantity`, and `status`
- `product_images`: image URL records for product media
- `delivery_windows`: active scheduled delivery windows used for customer availability

Products appear available to customers only when:

- `products.active = true`
- `products.delivery_eligible = true`
- availability exists for the active delivery window
- availability status is `active`
- `available_quantity > reserved_quantity`

Admin catalog pages:

- `/admin/products`
- `/admin/products/new`
- `/admin/products/{id}`
- `/admin/categories`
- `/admin/availability`

Customer catalog pages:

- `/customer/catalog`
- `/customer/product/{id}`
- `/customer/category/{id}`

## Sample Catalog Data

Startup seeds sample categories, one sample producer, one active Seattle delivery window, and a few products when the product table is empty. This makes a fresh local or Docker setup immediately reviewable.

## Inventory Scope

Inventory is deliberately simple for v1:

- available quantity
- reserved quantity
- active/inactive/sold-out status
- delivery-window-based availability
- low inventory view/export

Future phases can add subscriptions, recurring weekly boxes, producer self-service, dynamic pricing, advanced inventory, multiple regions, and richer delivery planning without replacing the v1 catalog structure.

## Docker

Copy the environment file:

```bash
cp .env.example .env
```

Build and run:

```bash
docker compose up --build
```

The app will be available at `http://127.0.0.1:8000`.

## Production startup

Recommended production command:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

For higher traffic, add workers based on server size:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000
```

## Linux deployment notes

1. Install Python 3.11+ and Git on the server.
2. Clone the repository.
3. Create `.env` from `.env.example`.
4. Set `DATABASE_URL` for SQLite or PostgreSQL.
5. Install dependencies in a virtual environment.
6. Run `python -c "from app.database import init_db; init_db()"`.
7. Start with gunicorn directly, Docker Compose, or a systemd service.
8. Put Nginx or another reverse proxy in front of port `8000`.
9. Monitor `/health` from your uptime or load balancer checks.

For SQLite on Linux, make sure the deployment user can write to the `data/` directory. For PostgreSQL, keep credentials in `.env` and never commit them.

## Tests

```bash
pytest
```
