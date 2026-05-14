# Farmsource V1 Release Notes

## Implemented Features

- FastAPI application foundation with environment-based configuration.
- Producer/source database with CSV import and duplicate detection.
- Product categories, product catalog, delivery-window availability, and inventory reservation.
- Customer catalog, product detail, cart, checkout, order confirmation, and order lookup.
- Stripe Checkout redirect flow with local no-key development fallback.
- Admin dashboard for producers, catalog, orders, customers, delivery windows, drivers, routes, exports, waitlist leads, and marketing content.
- Route-based delivery workflow with driver login, assigned routes, stop details, delivery/failed/skipped status updates, and route payout estimates.
- Public marketing site with waitlist, producer interest, driver interest, SEO metadata, sitemap, and robots file.
- AI-assisted marketing content drafts with captions, hashtags, scripts, video prompts, approval states, scheduling, and Excel export.
- Mobile-first customer and driver web apps with PWA manifest, service worker placeholder, focused bottom navigation, and Capacitor wrapper setup for shop and driver shells.
- Demo seed command: `python seed_demo.py`, with guarded local reset: `python seed_demo.py --reset`.
- Phase 10 readiness tests for database, imports, catalog, checkout, mocked Stripe, capacity, routing, driver completion, exports, public forms, marketing, PWA, and mobile wrapper config.

## Known Limitations

- No native iOS/Android builds yet.
- Mobile apps are PWA/web-wrapper ready.
- No live GPS tracking.
- No automated route optimization.
- No automatic social posting.
- No producer self-service portal.
- No advanced subscription model yet.
- Stripe webhook verification is a placeholder.
- SQLite is the default local database; PostgreSQL is recommended before larger production use.

## Recommended Next Steps

- Run a controlled local end-to-end pilot rehearsal with demo data.
- Replace default admin and driver passwords before any shared deployment.
- Configure Stripe test keys privately and run hosted Checkout in test mode.
- Deploy behind HTTPS with `SESSION_COOKIE_SECURE=true`.
- Add Alembic migrations before production data grows.
- Prepare PostgreSQL migration for multi-user pilot operations.
- Add manual operating procedures for failed payments, failed deliveries, refunds, and customer support.

## Pilot Readiness Notes

Farmsource v1 is ready for controlled pilot validation with internal users and invited testers. The system is intentionally manual where operational risk is high: social posting, route optimization, refunds, delivery exceptions, and producer onboarding still require human review.
