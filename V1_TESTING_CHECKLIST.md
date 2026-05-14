# Farmsource V1 Testing Checklist

Use this checklist for local or Docker pilot validation before inviting real test users.

## Setup

- Create `.env` from `.env.example`.
- Confirm `.env` is not committed and contains only local/test credentials.
- Run `python seed_demo.py`.
- Run `pytest`.
- Run `docker compose config --quiet`.
- Start the app only when ready to test manually.

## Admin

- Log in at `/admin/login` with `admin@farmsource.local` / `ChangeMe123!`.
- Open `/admin/dashboard`.
- Create or review producers from `/admin/producers`.
- Import a producer CSV from `/admin/imports`.
- Create product categories from `/admin/categories`.
- Create products from `/admin/products`.
- Create availability from `/admin/availability`.
- Create delivery windows from `/admin/delivery-windows`.

## Customer Ordering

- Open `/customer/catalog` on a phone-sized viewport.
- Open a product detail page.
- Add a product to cart.
- Open `/customer/cart`.
- Open `/customer/checkout`.
- Select a delivery window.
- Complete checkout in local no-key mode or Stripe test mode.
- Confirm the order confirmation page loads.
- Confirm `/customer/orders?email=...` finds the order.

## Stripe

- Confirm `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` come from environment variables.
- Confirm `.env.example` has blank Stripe placeholders only.
- Confirm no real Stripe secret key is committed.
- Test no-key local checkout redirect.
- Test Stripe Checkout with a test secret key in a private `.env`.
- Confirm `/customer/payment-success` marks orders paid.
- Confirm `/customer/payment-cancelled` cancels unpaid orders.
- Confirm `/customer/stripe/webhook` exists as a placeholder.

## Driver Route

- Admin creates a route from `/admin/routes/new`.
- Admin adds a paid order as a route stop.
- Admin assigns `driver@example.com`.
- Driver logs in at `/driver/login` with `Driver123!`.
- Driver opens `/driver/routes`.
- Driver opens the active route.
- Driver opens a stop.
- Driver marks the stop delivered.
- Confirm the order becomes `delivered`.

## Exports

- Download producer exports.
- Download product and availability exports.
- Download order exports.
- Download route, delivery summary, payout, completed route, and failed delivery exports.
- Download driver exports.
- Download waitlist, producer interest, and driver interest exports.
- Download marketing content export.

## Public Website

- Open `/`, `/how-it-works`, `/for-customers`, `/for-producers`, `/for-drivers`, `/about`, `/waitlist`, `/contact`, and `/faq`.
- Submit customer waitlist form.
- Submit producer interest form.
- Submit driver interest form.
- Confirm `/robots.txt` and `/sitemap.xml` load.
- Confirm public copy describes nationwide regional use and does not frame Seattle as the only pilot location.

## Deployment

- Confirm Linux-friendly paths are used.
- Confirm static files load.
- Confirm `/static/manifest.json` loads.
- Confirm `/static/service-worker.js` loads without breaking the app.
- Confirm Docker Compose config is valid.
- Confirm production startup command is documented.
- Confirm Nginx, HTTPS, and systemd recommendations are documented.
