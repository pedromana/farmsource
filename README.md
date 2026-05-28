# Farmsource

Farmsource is a v1 foundation for a local farm-to-consumer marketplace designed for regional launches across the United States. It is built around scheduled delivery routes, not instant delivery.

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
- Public marketing website, waitlist, and onboarding forms for regional launches
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
- pandas and openpyxl dependencies for Excel export work
- Rule-based ordering readiness classification for ecommerce, CSA, platform stores, contact-only pages, social media, and unknown destinations
- Curated v1 product catalog with simple delivery-window inventory
- Customer ordering flow with cart, scheduled delivery windows, Stripe-hosted payment, and order status pages
- Simple session-based admin login for v1 operations
- Driver route execution app with assigned routes, stop details, status updates, and payout estimates
- Public lead collection for customers, producers, drivers, and contact inquiries

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

Local setup remains supported, but remote development on a Linux server is now the recommended daily workflow so Windows does not need to run the full stack. See `REMOTE_DEV_SETUP.md` for the server-based Docker Compose workflow with Postgres, SSH tunneling, IDE setup, logs, tests, and troubleshooting.

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

To load or refresh local demo data for pilot testing, run:

```bash
python seed_demo.py
```

For a clean local SQLite demo database only, use:

```bash
python seed_demo.py --reset
```

The reset command is guarded so it only runs when `APP_ENV` is local/development/test and `DATABASE_URL` points to SQLite. It is intended for local pilot rehearsals, not production.

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
- Unassign a route from a driver and return it to the unassigned route list.
- Review suggested drivers scored by territory/region match and current active route load.
- Accept one suggested driver for a route.
- Accept all current route-driver suggestions from the route list.
- Review priority reassignment routes first when a driver declines a route.

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

Drivers can decline an assigned route from the route detail screen. Declining removes the route from that driver's app, clears the route assignment, returns the route to `planned`, marks it as priority for reassignment, and records the decline note for admin review.

When a stop is marked delivered, the stop status changes to `delivered`, the order status changes to `delivered`, and `delivered_at` is recorded. When all stops are completed as delivered, failed, or skipped, the route becomes `completed`.

The payout model is intentionally simple: base route pay plus route bonus plus optional tip placeholder. No payroll integration or automatic payouts are included in v1.

Future delivery expansion can add GPS tracking, route optimization, driver notifications, customer tracking, proof photo uploads, native mobile wrapping, navigation integrations, driver onboarding, and automated payouts.

## Public Website And Onboarding

Phase 7 adds the public-facing Farmsource website for regional launch demand. This is separate from the customer ordering app and focuses on awareness, trust, onboarding, and lead collection.

Public pages:

- `/`
- `/how-it-works`
- `/for-customers`
- `/for-producers`
- `/for-drivers`
- `/about`
- `/waitlist`
- `/contact`
- `/faq`

Lead tables:

- `waitlist_signups`: customer, producer, and driver waitlist signups
- `producer_interests`: producer onboarding interest submissions
- `driver_interests`: driver onboarding interest submissions
- `contact_messages`: simple contact form submissions

Onboarding flows:

1. Customers join the Farmsource launch waitlist from `/waitlist` or `/for-customers`.
2. Producers submit business and product information from `/for-producers`.
3. Drivers submit territory, vehicle, and availability information from `/for-drivers`.
4. General inquiries are saved from `/contact`.
5. Admin reviews submissions from `/admin/waitlist`, `/admin/producers/interests`, and `/admin/drivers/interests`.
6. Admin exports lead lists from `/admin/exports/waitlist`, `/admin/exports/producer-interests`, and `/admin/exports/driver-interests`.

The public pages include SEO-friendly page titles, meta descriptions, Open Graph placeholders, structured data, semantic page structure, nationwide launch messaging, and placeholders for Instagram, producer spotlights, featured farms, and seasonal produce highlights.

Future marketing expansion can add SEO content/blog posts, producer profiles, native app download pages, referrals, promo codes, marketing integrations, automated onboarding, and richer local landing pages by neighborhood or region.

## AI Marketing Assistant

Phase 8 adds a lightweight AI-assisted marketing workflow for planning daily social content. It generates draft ideas, captions, hashtags, short-video prompts, short scripts, and calls to action, then stores them for manual review.

Admin pages:

- `/admin/marketing`: marketing dashboard with filters for content type, audience, platform, and status
- `/admin/marketing/new`: create and generate a new content draft
- `/admin/marketing/{id}`: review, edit, approve, reject, schedule, or mark manually posted
- `/admin/marketing/calendar`: simple schedule view for planned, draft, and approved posts
- `/admin/marketing/drafts`: review queue for generated drafts

Marketing tables:

- `marketing_content`: generated draft content, captions, hashtags, video prompts, scripts, approval status, and scheduling fields
- `marketing_content_assets`: optional reference asset URLs for drafts
- `marketing_content_schedules`: planned manual posting dates, platforms, and posting status

The v1 workflow is intentionally manual:

1. Generate an idea, caption, hashtags, video prompt, script, and CTA.
2. Save the draft.
3. Review and edit the generated content.
4. Approve or reject the draft.
5. Schedule approved content.
6. Post manually outside Farmsource.
7. Mark the content as posted after manual posting.

No automatic Instagram, TikTok, Facebook, or YouTube posting is included. No autonomous agent, video rendering, analytics dashboard, engagement tracking, or social API integration is included in this phase.

AI generation is provider-neutral. The current implementation uses deterministic mock generation under `app/services/ai_services/`:

- `content_generator.py`: orchestrates ideas, full drafts, status constants, and CTA-ready output
- `caption_generator.py`: captions and audience-specific CTAs
- `hashtag_generator.py`: dynamic theme and audience hashtag sets
- `video_prompt_generator.py`: vertical short-video prompts and scripts

Set `MARKETING_AI_PROVIDER` in the environment for future provider selection. The current default is `mock`; future phases can add OpenAI, Claude, Gemini, image generation, video generation, automated posting, social analytics, engagement tracking, A/B testing, producer-generated content, and recommendation services without changing the admin workflow.

## Mobile-First Customer And Driver Apps

Phase 9 keeps one shared FastAPI/Jinja codebase and optimizes the customer and driver experiences as app-like mobile web applications. No separate iOS, Android, React Native, or Flutter app is included in v1.

Customer mobile routes:

- `/customer/catalog`
- `/customer/product/{id}`
- `/customer/cart`
- `/customer/checkout`
- `/customer/orders`
- `/customer/order/{id}`

Driver mobile routes:

- `/driver`
- `/driver/routes`
- `/driver/route/{route_id}`
- `/driver/stop/{stop_id}`

Mobile UX improvements include bottom app navigation, touch-sized buttons, sticky cart and checkout actions, app-level tabs, lazy-loaded product images, inline cart updates, toast feedback, loading button states, better empty states, and simplified driver route/stop workflows.

The driver workflow remains:

1. Open the driver app.
2. View assigned routes.
3. Open an active route.
4. Review stop progress and stop list.
5. Open a stop.
6. Mark delivered or failed.
7. Return to the route and continue to the next stop.

## PWA Setup

The app includes basic Progressive Web App support:

- `/static/manifest.json`: install metadata, standalone display mode, app shortcuts, theme/background colors, and icon placeholders
- `/static/js/service-worker.js`: static asset cache placeholder for CSS, JS, and icon assets
- `/static/icons/icon.svg`: install icon placeholder
- `/static/icons/splash.svg`: splash screen placeholder

The service worker intentionally avoids full offline synchronization, push notifications, advanced caching, and background sync. Those are future phases because ordering, checkout, and delivery completion need careful conflict handling before offline mode is safe.

## Mobile Wrapping Strategy

Recommended future Capacitor path:

1. Keep Farmsource as the source of truth web app.
2. Configure Capacitor to load the production HTTPS URL or a bundled web build if the frontend is later separated.
3. Add native plugins only when needed: push notifications, GPS, camera proof uploads, deep links, and secure storage.
4. Test the same customer and driver flows in mobile Safari, Chrome, Capacitor iOS, and Capacitor Android.
5. Add App Store and Play Store packaging only after PWA workflows are stable in production.

Cordova, Trusted Web Activity, or similar wrappers can follow the same approach: wrap the mobile-first web routes, keep API and operations logic in the shared backend, and avoid duplicating business logic in native clients.

## Mobile App Wrapper

Phase 9B adds Capacitor wrapper setup for two thin native shells over the existing Farmsource mobile-first web app. These wrappers do not duplicate customer code, driver code, routing, checkout logic, delivery workflow, or business rules. They load focused areas of the same Farmsource backend/frontend.

Capacitor configuration:

- Customer app name: `Farmsource Shop`
- Customer app id: `com.farmsource.shop`
- Customer start path: `/customer/catalog`
- Driver app name: `Farmsource Driver`
- Driver app id: `com.farmsource.driver`
- Driver start path: `/driver`
- Config file: `capacitor.config.ts`
- Web directory: `app/static`
- Default local mobile server URL: `http://10.0.2.2:8001`
- App mode selector: `FARMSOURCE_APP_MODE=shop` or `FARMSOURCE_APP_MODE=driver`
- Override URL: set `FARMSOURCE_MOBILE_SERVER_URL` before syncing/building

The default URL is intended for Android emulator testing against a Farmsource server running on the host machine at port `8001`. For a physical Android device, iOS simulator, iOS device, or production app, use a reachable URL:

```bash
FARMSOURCE_MOBILE_SERVER_URL=https://your-domain.example npx cap sync
```

On Windows PowerShell:

```powershell
$env:FARMSOURCE_MOBILE_SERVER_URL="https://your-domain.example"
npm run cap:sync:shop
```

Initial wrapper setup commands:

```bash
npm install
npx cap init Farmsource com.farmsource.app --web-dir app/static
npx cap add android
npx cap add ios
npx cap sync
```

The repo already includes generated `android/` and `ios/` wrapper projects. Use the mode-specific scripts after changing `capacitor.config.ts`, static assets, icons, or the target server URL:

```bash
npm run cap:sync:shop
npm run cap:sync:driver
```

Android workflow:

```bash
npm install
npm run android:build:shop
npm run android:build:driver
npx cap open android
```

The current Android wrapper project is reused for both apps. The mode-specific scripts update the Android application id and app label before building:

- Shop debug APK: build with `npm run android:build:shop`, package id `com.farmsource.shop`
- Driver debug APK: build with `npm run android:build:driver`, package id `com.farmsource.driver`

Android Studio can then run the app on an emulator or attached device. For local emulator testing, start Farmsource locally first:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then use the default Capacitor URL `http://10.0.2.2:8001`. For MuMuPlayer with `adb reverse`, set `FARMSOURCE_MOBILE_SERVER_URL=http://127.0.0.1:8001`, run the mode-specific build, and reverse the port:

```bash
adb reverse tcp:8001 tcp:8001
```

For a physical Android device, set `FARMSOURCE_MOBILE_SERVER_URL` to the computer's LAN URL or a deployed HTTPS URL, then run the mode-specific build.

Android build outputs are created by Android Studio or Gradle:

- Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`
- Release APK: `android/app/build/outputs/apk/release/app-release.apk`
- Release AAB: `android/app/build/outputs/bundle/release/app-release.aab`

Android prerequisites:

- Android Studio
- Android SDK
- JDK with `JAVA_HOME` set
- Emulator image or physical Android device with USB debugging enabled

iOS workflow:

```bash
npm install
npx cap sync ios
npx cap open ios
```

iOS builds require macOS and Xcode. The iOS project structure is present in `ios/`, but simulator/device builds must be performed on a Mac with Xcode installed. In Xcode, select the `App` scheme, choose a simulator or connected device, set signing/team settings, and run.

Future iOS distribution path:

1. Configure bundle signing in Xcode.
2. Archive the app.
3. Upload through Xcode Organizer or Transporter.
4. Test through TestFlight.
5. Submit to the App Store after privacy, permissions, and review metadata are ready.

Current native assets are placeholders:

- Web/PWA icon: `app/static/icons/icon.svg`
- Web/PWA splash placeholder: `app/static/icons/splash.svg`
- Android generated launcher/splash resources under `android/app/src/main/res/`
- iOS generated app icon/splash resources under `ios/App/App/Assets.xcassets/`

Future native API enhancements can add push notifications, camera proof-of-delivery uploads, GPS route support, offline queues, background sync, deep linking, and App Store/Play Store-specific configuration.

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

For production, start from `.env.production.example`, set a long random `SESSION_SECRET_KEY`, set `SESSION_COOKIE_SECURE=true` behind HTTPS, replace the default admin password, and configure Stripe keys if checkout should use live Stripe.

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
3. Create `.env` from `.env.production.example`.
4. Set `DATABASE_URL` for SQLite or PostgreSQL.
5. Install dependencies in a virtual environment.
6. Run `python -c "from app.database import init_db; init_db()"`.
7. Start with gunicorn directly, Docker Compose, or a systemd service.
8. Put Nginx or another reverse proxy in front of port `8000`.
9. Monitor `/health` from your uptime or load balancer checks.

For SQLite on Linux, make sure the deployment user can write to the `data/` directory. For PostgreSQL, keep credentials in `.env` and never commit them.

Recommended Nginx setup:

- terminate HTTPS with Let's Encrypt or another certificate provider
- proxy `https://your-domain.example` to `http://127.0.0.1:8000`
- forward `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto`
- serve static files through the app for v1, or offload `/static/` to Nginx later if traffic grows

Systemd option:

```ini
[Unit]
Description=Farmsource
After=network.target

[Service]
WorkingDirectory=/opt/farmsource
EnvironmentFile=/opt/farmsource/.env
ExecStart=/opt/farmsource/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8000 --access-logfile - --error-logfile -
Restart=always
User=farmsource

[Install]
WantedBy=multi-user.target
```

Future deployment work can add Alembic migrations, PostgreSQL as the default production database, object storage for proof photos/assets, Redis-backed rate limiting, structured JSON logs, and blue/green deploys.

## Tests

```bash
pytest
```

Phase 10 stabilization added v1 readiness coverage for the database connection, producer duplicate detection, product/category creation, delivery window capacity, mocked Stripe Checkout session creation, route assignment, driver stop completion, Excel exports, waitlist forms, marketing content creation, PWA/mobile wrappers, and a compact customer-to-driver delivery flow.

Useful validation commands:

```bash
python seed_demo.py
pytest
docker compose config --quiet
```

Additional operator docs:

- `REMOTE_DEV_SETUP.md`: remote Linux development workflow for VS Code Remote SSH or PyCharm remote development
- `PRODUCTION_OPERATIONS.md`: Alembic migration and Postgres backup/restore commands
- `LAUNCH_CHECKLIST.md`: production, Stripe, operations, outreach, and pilot readiness checklist for `farmsourcemarket.com`
- `NEXT_7_DAY_PLAN.md`: one-week solo founder plan for production readiness and first producer outreach
- `V1_TESTING_CHECKLIST.md`: manual and automated checks for local pilot testing
- `V1_RELEASE_NOTES.md`: implemented v1 features, limitations, and next steps
- `PILOT_PLAN.md`: first pilot rehearsal flow and manual fallback procedures
