# Farmsource Project Context

Load keyword: `LOAD_FARMSOURCE_CONTEXT`

Use this file only for the Farmsource project in this repository. Do not use this context for unrelated projects.

## How To Use This File

When starting a future session for this project, say:

```text
LOAD_FARMSOURCE_CONTEXT
```

Then ask the assistant to read this file before making project decisions.

## Current Context Source

Paste the summarized context from the Farmsource ChatGPT project below this line.

---

## Project Summary From ChatGPT

Farmsource is a local farm-to-consumer marketplace being built first for the Seattle region.

The concept is similar to Instacart, but instead of grocery store shopping, Farmsource connects customers directly with local farms, producers, and fresh food suppliers. The goal is to help customers buy fresh produce locally while giving small producers a better digital sales and delivery channel.

Farmsource is planned as a marketplace with:

- Customer-facing ordering app
- Producer/farm supply side
- Delivery/driver operations
- Admin/operations dashboard
- Stripe payments
- Local producer database
- Scheduled route-based delivery
- AI marketing system for customer acquisition

The first version should not try to be a full grocery marketplace. It should be a focused MVP that proves whether customers want curated local produce delivery and whether producers are willing to participate.

## Current Business Priority

The current priority is not to perfect the platform. The priority is to launch a working MVP in production, validate producer supply, validate customer interest, and prove the delivery model can work locally.

## Product Direction

The latest direction is a scheduled local produce delivery marketplace.

Customers should be able to browse available produce or curated boxes, place an order, pay online, and receive delivery during scheduled windows.

For V1, Farmsource should avoid instant delivery. The model should use neighborhood batching and predictable routes so delivery costs stay controlled.

## What Has Already Been Built

The current v1 codebase includes:

- Producer/source database
- CSV import
- Product catalog
- Customer ordering
- Stripe Checkout
- Admin dashboard
- Driver route workflow
- Public website/waitlist
- AI marketing assistant
- PWA/mobile-first customer and driver experiences
- Deployment-ready Docker/Linux structure
- Launch readiness checklist and 7-day operational plan
- Standalone browser-based founder priority board

## What Should Not Be Prioritized Right Now

Do not prioritize:

- Complex driver dispatch
- Real-time delivery tracking
- Full producer self-service portal
- Advanced inventory automation
- Multi-city expansion
- Native mobile apps
- Complex subscription logic
- Overbuilt AI features
- Full Instacart-style marketplace behavior

## Operational Priorities

Farmsource V1 should work more like a weekly local delivery route than an on-demand app.

The expected model:

1. Producers provide available inventory.
2. Farmsource aggregates available products into curated listings or produce boxes.
3. Customers order before a cutoff time.
4. Orders are packed or aggregated.
5. Drivers deliver by neighborhood/route during scheduled windows.
6. Admin manages orders, producers, delivery routes, and payment status.

Immediate operational priority:

1. Onboard enough producers to create credible supply.
2. Attract enough early customers to validate demand.
3. Set up production in parallel.
4. Run a complete test order and delivery simulation.

## Stripe / Payment Status

Stripe is the selected payment provider. The MVP should support the core path:

Customer browses products or produce boxes -> places order -> pays with Stripe -> admin sees the order -> operations assigns it to a delivery route -> order is fulfilled and delivered.

Live Stripe keys must never be committed. Stripe webhook verification is not the main business priority, but it should be reviewed before real paid orders if possible.

## Production Deployment Status

Production should run on a Linux server using Docker/Docker Compose, with Nginx and HTTPS in front of the app. The likely domain is `farmsourcemarket.com`.

Production setup should happen in parallel with producer outreach and customer demand work, not block all operational progress.

## Producer Outreach Strategy

Producer outreach should start in parallel with technical setup.

Initial approach:

1. Upload producer/farm prospects from CSV into the local database.
2. Filter for producers most likely to participate.
3. Focus first on Seattle-region farms/producers with clear local relevance and manageable fulfillment.
4. Contact a small first batch rather than trying to onboard everyone.
5. Validate whether producers are willing to provide inventory and participate in scheduled local delivery.

## Customer Acquisition Strategy

Use the public website, waitlist, local/community channels, producer relationships, and AI-assisted marketing drafts to validate early customer interest.

The goal is not broad marketing scale yet. The goal is to collect enough local interest to justify a first controlled delivery test.

## Decisions Already Made

- Start in the Seattle region.
- Use `farmsourcemarket.com` as the likely domain.
- Use Stripe for payments.
- Use a Linux server for production.
- Start producer outreach in parallel with technical setup.
- Upload producer/farm prospects from CSV into the local database.
- Avoid on-demand gig delivery for V1.
- Use scheduled route-based delivery.
- Keep operations local and manageable.
- Build for validation first, scale later.

## Next Recommended Steps

The next coding focus should be the smallest usable production flow:

Customer browses products or produce boxes -> places order -> pays with Stripe -> admin sees the order -> operations can assign it to a delivery route -> order can be fulfilled and delivered.

That is the MVP core.

Near-term work should favor operational preparation:

1. Farm onboarding.
2. Customer demand/waitlist.
3. Production deployment.
4. Stripe test/live readiness.
5. First delivery simulation.

## Current Execution Priority Model

Use this priority model when deciding next steps or reducing scope.

Primary principle: the biggest risk right now is not technical. It is failing to validate producer supply and operational logistics early.

Prioritized startup sequence:

1. Phase 1 - Immediate Foundation: secure core infrastructure, create the producer database, and start producer outreach immediately. Producer outreach should happen before the app is perfect.
2. Phase 2 - MVP Backend: keep only the backend needed for users, producers, products, orders, payments, delivery windows, routes, Stripe Checkout, payment confirmation, and minimal admin operations.
3. Phase 3 - Customer MVP: keep customer ordering simple: browse produce, add to cart, checkout, select delivery window, receive confirmation. Prioritize stability and mobile usability over polish.
4. Phase 4 - Production Launch Preparation: deploy the first production version, configure production DB/domain/SSL/Stripe/logging/backups, and run a small pilot with 10-30 customers, a small producer group, one region, and one or two delivery days.
5. Phase 5 - Customer Acquisition: after operations work reliably, launch AI marketing, then referral/repeat ordering and produce box/subscription incentives.

Immediate next 72-hour focus:

- Day 1: server setup, database setup, domain setup, producer CSV import.
- Day 2: producer outreach starts, core schema review/creation, Stripe integration review.
- Day 3: basic admin dashboard review, product/order API review, initial customer ordering flow test.

Do not prioritize now:

- Native mobile apps
- Real-time tracking
- Advanced AI agents
- Multi-region scaling
- Marketplace complexity
- Automated route optimization
- Producer self-service portals
- Enterprise architecture
- Overengineering

Keep `LAUNCH_CHECKLIST.md` as a complete audit checklist. Use `launch-checklist.html` as the simplified prioritized startup checklist.
