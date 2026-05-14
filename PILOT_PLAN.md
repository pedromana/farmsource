# Farmsource Pilot Plan

## First Test Flow

1. Run `python seed_demo.py`.
2. Run `pytest`.
3. Start the app locally or with Docker.
4. Log in as admin.
5. Confirm producers, categories, products, availability, delivery windows, drivers, routes, waitlist leads, and marketing drafts are visible.

## First Producer Onboarding Flow

1. Add one real producer manually in `/admin/producers`.
2. Confirm contact, city/state, products, qualification, and ordering destination fields.
3. Add one or two products connected to that producer.
4. Add availability for the next delivery window.
5. Export producer and product records for review.

## First Customer Test Flow

1. Open `/customer/catalog` on a phone.
2. Add one produce box and one add-on item to cart.
3. Complete checkout with local no-key mode or Stripe test mode.
4. Confirm the order appears in admin.
5. Confirm the customer can find the order from `/customer/orders`.

## First Delivery Simulation

1. Admin creates a route for the test delivery window.
2. Admin assigns the paid test order to the route.
3. Admin assigns a driver.
4. Admin confirms route manifest export works.
5. Driver marks the stop delivered.
6. Admin confirms the order is delivered and route progress is complete.

## First Driver Test Flow

1. Driver logs in at `/driver/login`.
2. Driver opens assigned routes.
3. Driver opens the route detail page.
4. Driver opens the stop detail page.
5. Driver marks the stop delivered, failed, or skipped.
6. Admin reviews route progress and delivery summary export.

## Launch Risks To Watch

- Inventory reserved for unpaid or cancelled orders.
- Delivery window capacity mismatches.
- Manual route sequencing errors.
- Wrong driver assignment.
- Customer address or phone entry mistakes.
- Stripe test/live key confusion.
- Public waitlist spam.
- Mobile browser differences on older devices.

## Manual Fallback Procedures

- If checkout fails, create the order manually after payment is confirmed outside the app.
- If route assignment fails, export orders and text the driver a manual stop list.
- If driver app is unavailable, record delivery status by phone and update route stops in admin.
- If inventory is wrong, pause product availability and contact affected customers manually.
- If marketing generation is poor, edit or reject the draft before posting manually.
