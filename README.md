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
- Admin operations dashboard at `/admin/dashboard`
- Admin order, customer, driver, route, delivery-window, and export management
- Scheduled route planning and mobile-friendly driver delivery workflow
- Customer catalog at `/customer/catalog`
- Customer cart and checkout at `/customer/cart` and `/customer/checkout`
- Stripe Checkout redirect flow with local no-key simulation for development
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
- Customer ordering flow with cart, scheduled delivery windows, Stripe-hosted payment, and order status pages
- Simple session-based admin login for v1 operations
- Driver route execution app with assigned routes, stop details, status updates, and payout estimates

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

## Customer Ordering

Phase 4 adds a mobile-friendly customer ordering flow:

1. Browse the catalog at `/customer/catalog`.
2. View products at `/customer/product/{id}`.
3. Add products to the cart.
4. Review the cart at `/customer/cart`.
5. Enter delivery details and select a delivery window at `/customer/checkout`.
6. Continue to Stripe-hosted Checkout.
7. Return to `/customer/payment-success`.
8. View confirmation at `/customer/order-confirmation/{order_id}`.
9. View order status at `/customer/order/{id}` or search by email at `/customer/orders`.

Order status values:

- `pending`
- `confirmed`
- `packed`
- `assigned_to_route`
- `out_for_delivery`
- `delivered`
- `cancelled`

Payment status values:

- `unpaid`
- `pending`
- `paid`
- `failed`
- `refunded`

## Stripe Setup

Stripe uses hosted Checkout only. Farmsource does not collect card numbers or render custom credit card fields.

Add these values to `.env`:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
APP_BASE_URL=http://127.0.0.1:8000
```

For local development without `STRIPE_SECRET_KEY`, the app redirects to a local simulated payment success URL so the full order flow can be tested. With a real Stripe secret key, the checkout route creates a Stripe Checkout Session and redirects the customer to Stripe.

A placeholder webhook endpoint exists at:

```text
POST /stripe/webhook
```

Future work should add Stripe signature verification and event handling for asynchronous payment updates.

## Delivery Window Logic

Customers only see delivery windows where:

- `active = true`
- `current_order_count < max_orders`

When checkout starts, Farmsource validates product inventory for the selected delivery window, creates a pending order, increments `reserved_quantity`, and increments the delivery window order count. If payment is cancelled, unpaid order inventory is released.

## Mobile Wrapper Readiness

The customer app is a responsive, PWA-friendly web app. Future phases can wrap it with Capacitor or a similar tool and add native features such as saved customer accounts, push notifications, subscriptions, promo codes, loyalty, and recurring weekly box ordering.

## Admin Operations Dashboard

Phase 5 adds the v1 manual operations dashboard for running the Seattle pilot. Admin pages are protected by a simple session login:

```text
/admin/login
/admin/logout
```

Default local credentials are seeded from environment variables:

```env
ADMIN_DEFAULT_EMAIL=admin@farmsource.local
ADMIN_DEFAULT_PASSWORD=ChangeMe123!
SESSION_SECRET_KEY=change-this-before-production
```

Change these values before any shared or production deployment. The first app startup seeds the default admin user when no admin exists.

Operations pages:

- `/admin/dashboard` shows producer, product, order, route, driver, sales, delivery-window, and low-inventory operating metrics.
- `/admin/orders` supports search/filtering, order detail review, status updates, route assignment, internal notes, and Excel export.
- `/admin/customers` lists customer delivery/contact records.
- `/admin/drivers` manages driver profiles, territories, vehicles, active status, and notes.
- `/admin/routes` creates routes, assigns drivers and delivery windows, adds orders as stops, reorders stops, and updates stop statuses.
- `/admin/delivery-windows` manages scheduled delivery dates, regions, active status, and order capacity.
- `/admin/exports` provides Excel exports for orders, routes, producers, products, delivery windows, customers, and drivers.

The intended v1 operating workflow is:

1. Import or manually manage producers.
2. Add curated products and delivery-window availability.
3. Create delivery windows for the week.
4. Customers place orders.
5. Admin reviews orders and payment state.
6. Admin creates routes and assigns drivers.
7. Admin adds orders to route stops and manages stop sequence.
8. Drivers complete deliveries.
9. Admin exports operational reports as needed.

Route statuses are `planned`, `assigned`, `in_progress`, `completed`, and `cancelled`. Stop statuses are `pending`, `delivered`, `failed`, and `skipped`.

This is intentionally simple. Future phases can add richer permissions, producer and driver self-service, route optimization, notifications, analytics, warehouse hubs, and multi-region operations without replacing the current tables.

## Route-Based Delivery

Phase 6 expands the scheduled delivery system. Farmsource remains a pre-planned, route-based operation, not an instant delivery marketplace.

Delivery tables:

- `drivers`: driver profiles, territory, vehicle, active status, and notes
- `routes`: assigned delivery window, driver, route status, stop/order estimates, route pay, bonus, and notes
- `route_stops`: stop sequence, customer/address snapshot, delivery notes, driver notes, delivery status, failed reason, and proof URL placeholder
- `driver_payouts`: base route pay, bonus, tip placeholder, total pay, payout status, and payout notes

Route statuses are:

- `planned`
- `assigned`
- `in_progress`
- `completed`
- `cancelled`

Stop statuses are:

- `pending`
- `delivered`
- `failed`
- `skipped`

Payout statuses are:

- `pending`
- `approved`
- `paid`

## Route Workflow

The v1 operating flow is:

1. Admin creates delivery windows.
2. Customers place scheduled orders.
3. Admin creates a route at `/admin/routes/new`.
4. Admin assigns a delivery window and driver.
5. Admin opens `/admin/routes/{id}` and assigns orders as route stops.
6. Admin manually orders stops by editing stop sequence.
7. Driver opens the mobile web app and completes stops.
8. Admin reviews route progress, completed stops, failed deliveries, and payout status.

Admin route tools:

- `/admin/routes`
- `/admin/routes/new`
- `/admin/routes/{id}`
- `/admin/drivers`
- `/admin/drivers/{id}`
- `/admin/exports/route-manifest`
- `/admin/exports/delivery-summary`
- `/admin/exports/driver-payouts`
- `/admin/exports/completed-routes`
- `/admin/exports/failed-deliveries`

Route assignment options:

- Manually choose a driver from the route list or route detail page.
- Review suggested drivers scored by territory/region match and current active route load.
- Accept one suggested driver for a route.
- Accept all current route-driver suggestions from the route list.

Suggestions are deliberately advisory. They do not perform live dispatching, GPS matching, or route optimization.

## Driver Workflow

The driver app is a mobile-first web app that can later be wrapped with Capacitor or a similar tool.

Driver pages:

- `/driver/login`
- `/driver/routes`
- `/driver/route/{route_id}`
- `/driver/stop/{stop_id}`

For local sample data, use:

```text
driver@example.com
Driver123!
```

Drivers can view assigned routes, route progress, stops in sequence, delivery instructions, customer phone placeholder, ordered item summaries, and route payout estimate. On each stop, the driver can mark delivered, failed, skipped, add driver notes, add a failed reason, and store a proof-of-delivery URL placeholder.

Driver login is password protected. Admins can set or reset driver passwords from `/admin/drivers`; leaving the password field blank keeps the existing password.

When a stop is marked delivered, the stop status changes to `delivered`, the order status changes to `delivered`, and `delivered_at` is recorded. When all stops are completed as delivered, failed, or skipped, the route becomes `completed`.

The payout model is intentionally simple: base route pay plus route bonus plus optional tip placeholder. No payroll integration or automatic payouts are included in v1.

Future delivery expansion can add GPS tracking, route optimization, driver notifications, customer tracking, proof photo uploads, native mobile wrapping, navigation integrations, driver onboarding, and automated payouts.

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
