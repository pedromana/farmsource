# Farmsource Market Next 7 Day Plan

This plan assumes one solo founder preparing the current v1 for production launch readiness and first producer outreach. Keep the scope tight: deploy, test, prepare outreach, run one operational simulation, and document what remains.

## Day 1: Domain, Email, Stripe, And Config Review

- Confirm `farmsourcemarket.com` registrar access and DNS management.
- Create or confirm business email addresses, such as `hello@farmsourcemarket.com` and `producers@farmsourcemarket.com`.
- Activate Stripe account and complete required business details.
- Add Stripe test keys to local `.env`; do not commit them.
- Review `.env.production.example` and draft a production `.env` privately.
- Set planned production values:
  - `APP_ENV=production`
  - `APP_BASE_URL=https://farmsourcemarket.com`
  - `SESSION_COOKIE_SECURE=true`
  - a long random `SESSION_SECRET_KEY`
  - production admin email/password
- Run locally:
  - `python seed_demo.py`
  - `pytest`
  - `docker compose config --quiet`
- Update `LAUNCH_CHECKLIST.md` as facts are confirmed.

## Day 2: Linux Server And Docker Deployment

- Provision a small Linux server.
- Install Docker and Docker Compose.
- Clone the repository on the server.
- Create production `.env` on the server from `.env.production.example`.
- Configure persistent `data/` storage or decide on PostgreSQL if moving beyond SQLite now.
- Run:
  - `docker compose build`
  - `docker compose up -d`
- Confirm container logs are visible.
- Confirm Docker healthcheck status.
- Confirm `/health` works on the server IP before DNS cutover.

## Day 3: Production Smoke Testing

- Point DNS for `farmsourcemarket.com` to the server.
- Configure Nginx reverse proxy to the app container.
- Enable HTTPS/SSL.
- Test:
  - `/`
  - `/health`
  - `/customer/catalog`
  - `/admin/login`
  - `/driver/login`
  - `/static/manifest.json`
  - `/static/js/service-worker.js`
- Test customer checkout with Stripe test mode if the production environment is still safely configured for test keys.
- Verify payment success and cancellation flows.
- Verify waitlist, producer interest, driver interest, and contact forms.
- Confirm no real secrets are printed in logs or committed.

## Day 4: Producer CSV Import And Tagging

- Prepare the first producer CSV with names, URLs, locations, products, and contact details.
- Import CSV from `/admin/imports`.
- Review skipped duplicates and import errors.
- Filter producers by destination type, qualification, and online ordering readiness.
- Identify producers that are easiest to onboard first:
  - already sell online
  - have clear product availability
  - are close to the first delivery zone
  - have public contact information
- Select the first 25 producers for outreach.
- Export the producer list for outreach tracking.

## Day 5: Outreach Materials And Producer Offer

- Draft the producer offer in plain terms:
  - what Farmsource does
  - how orders are collected
  - how pickup/aggregation works
  - how payment/commission works
  - expected weekly time commitment
  - why early producers should join
- Draft the first outreach email.
- Draft a short follow-up email.
- Draft a short producer FAQ.
- Review `/for-producers` and the producer interest form.
- Create first marketing drafts in `/admin/marketing`:
  - producer recruitment
  - product spotlight
  - local food launch announcement
- Prepare a simple tracking sheet or CRM list for outreach status.

## Day 6: First Producer Outreach Batch

- Send outreach to the first 10-15 producers, not all 25 at once.
- Track status manually:
  - contacted
  - replied
  - interested
  - not interested
  - follow-up needed
  - meeting scheduled
- Reply quickly to interested producers.
- Capture objections and questions.
- Update producer notes in admin where useful.
- Draft improvements to the producer offer based on responses.
- Prepare the second batch for the next business day.

## Day 7: Operational Simulation And Next-Step Review

- Run a full internal simulation:
  - admin creates delivery window
  - admin confirms product availability
  - customer places order
  - Stripe test payment succeeds
  - admin creates route
  - admin assigns driver
  - driver marks stop delivered
  - admin exports reports
- Run the public lead forms one more time.
- Review logs for errors.
- Review `LAUNCH_CHECKLIST.md` and mark what is complete.
- Decide the next week plan:
  - continue producer outreach
  - start customer waitlist campaign
  - fix launch blockers
  - schedule first real delivery simulation
- Record a go/no-go status for production launch and producer outreach.
