# Farmsource Market Launch Checklist

## Current Status

- Last reviewed date: 2026-05-14
- Environment reviewed: local repository at `C:\Users\pmana\PycharmProjects\farmsource`, FastAPI app, SQLite default, Docker/Docker Compose config, PWA assets, Capacitor wrappers, Stripe Checkout code, and v1 readiness docs.
- Production readiness status: codebase is deployment-prepared, but production infrastructure and live domain configuration still need to be completed and verified.
- Stripe readiness status: Stripe Checkout integration exists and environment placeholders are present; live/test keys, hosted checkout testing, webhook secret planning, and live-mode procedures still need founder verification.
- Producer outreach readiness status: producer import, filtering, qualification, public producer interest form, and exports exist; outreach offer, first target list, email account, and cadence still need operating decisions.
- Main blockers:
  - Production server, DNS, Nginx, HTTPS, and production `.env` are not verified in this repo.
  - Live Stripe keys and webhook secret must be configured outside Git.
  - First delivery zone/window, producer outreach list, compensation model, and fallback procedures need final operating decisions.
  - Full production smoke test on `farmsourcemarket.com` still needs to be run after deployment.

## 1. Production Deployment Checklist

- [ ] Linux server ready
- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] domain DNS configured for `farmsourcemarket.com`
- [ ] Nginx reverse proxy configured
- [ ] HTTPS/SSL configured
- [ ] production `.env` created from `.env.production.example`
- [ ] `APP_BASE_URL=https://farmsourcemarket.com` set in production `.env`
- [ ] `SESSION_SECRET_KEY` replaced with a long random production secret
- [ ] `SESSION_COOKIE_SECURE=true` set for HTTPS
- [ ] default admin password replaced before public access
- [ ] database initialized
- [ ] writable `data/` directory or production database volume configured
- [ ] static files loading
- [ ] health endpoint working at `/health`
- [ ] PWA manifest working at `/static/manifest.json`
- [ ] service worker loads and does not break app navigation
- [ ] logs visible from Docker, systemd, or process manager
- [ ] Docker healthcheck passing
- [ ] backup plan defined for database and uploaded/exported files
- [ ] restore process tested or documented

## 2. Stripe Payment Checklist

- [ ] Stripe account activated
- [ ] Stripe business/profile information completed
- [ ] test keys configured locally
- [ ] live keys ready but not committed
- [ ] `STRIPE_SECRET_KEY` set in local/private `.env`
- [ ] `STRIPE_PUBLISHABLE_KEY` set in local/private `.env`
- [ ] `STRIPE_SECRET_KEY` set in production environment
- [ ] `STRIPE_PUBLISHABLE_KEY` set in production environment
- [ ] `.env` ignored by Git
- [ ] `.env.example` contains placeholders only
- [ ] checkout session creation tested
- [ ] payment success flow tested
- [ ] payment cancelled flow tested
- [ ] webhook endpoint reviewed
- [ ] webhook secret planned
- [ ] webhook signature verification added or explicitly deferred for first controlled pilot
- [ ] test order paid successfully
- [ ] order marked `paid` after successful payment
- [ ] production/live mode plan documented
- [ ] refund/manual support process documented

## 3. Admin Operations Checklist

- [ ] admin login working
- [ ] admin credentials changed for production
- [ ] producer management working
- [ ] CSV import working
- [ ] duplicate producer detection reviewed
- [ ] product category management working
- [ ] product management working
- [ ] product availability working
- [ ] delivery window management working
- [ ] order management working
- [ ] route assignment working
- [ ] driver assignment working
- [ ] exports working
- [ ] marketing content review working
- [ ] seed/demo data available with `python seed_demo.py`
- [ ] guarded reset reviewed with `python seed_demo.py --reset`

## 4. Customer App Checklist

- [ ] catalog loads on mobile
- [ ] product page works
- [ ] category page works
- [ ] cart works
- [ ] checkout works
- [ ] Stripe redirect works
- [ ] order confirmation works
- [ ] order history works
- [ ] delivery window selection works
- [ ] sold-out/full-window behavior reviewed
- [ ] PWA/mobile UX reviewed
- [ ] customer flow tested on iPhone Safari
- [ ] customer flow tested on Android Chrome

## 5. Driver App Checklist

- [ ] driver login/access works
- [ ] route list works
- [ ] route detail works
- [ ] stop detail works
- [ ] mark delivered works
- [ ] mark failed works
- [ ] mark skipped works
- [ ] driver notes work
- [ ] failed reason works
- [ ] route progress updates correctly
- [ ] completed routes behave correctly
- [ ] mobile UX reviewed
- [ ] driver flow tested on a real phone or Android emulator

## 6. Producer Outreach Checklist

- [ ] producer CSV imported
- [ ] producers tagged/filtered
- [ ] online-order-ready producers identified
- [ ] producer qualification rules reviewed
- [ ] outreach status fields reviewed
- [ ] producer offer drafted
- [ ] producer onboarding form working
- [ ] producer email account created
- [ ] outreach email drafted
- [ ] follow-up cadence defined
- [ ] first 25 producers selected
- [ ] producer objections/FAQ drafted
- [ ] producer pricing/commission plan documented
- [ ] producer pickup/aggregation expectations documented

## 7. Public Website / Brand Checklist

- [ ] `farmsourcemarket.com` purchased
- [ ] DNS configured
- [ ] homepage reviewed
- [ ] customer waitlist works
- [ ] producer interest form works
- [ ] driver interest form works
- [ ] contact form works
- [ ] SEO titles/meta reviewed
- [ ] sitemap reviewed at `/sitemap.xml`
- [ ] robots file reviewed at `/robots.txt`
- [ ] Instagram handle reserved
- [ ] business email configured
- [ ] public copy reviewed for nationwide positioning
- [ ] first producer/customer landing screenshots captured for outreach

## 8. Delivery Operations Checklist

- [ ] first delivery zone selected
- [ ] first delivery window selected
- [ ] route pay model defined
- [ ] driver compensation model documented
- [ ] aggregation/pickup model defined
- [ ] producer cutoff time defined
- [ ] customer order cutoff time defined
- [ ] manual fallback process defined
- [ ] failed delivery process defined
- [ ] customer support/refund process defined
- [ ] first delivery simulation completed
- [ ] route manifest export tested with real sample addresses

## 9. AI Marketing Checklist

- [ ] marketing assistant working
- [ ] content drafts generate correctly
- [ ] caption generation works
- [ ] hashtag generation works
- [ ] video prompt generation works
- [ ] content approval workflow works
- [ ] marketing calendar reviewed
- [ ] Instagram manual posting process defined
- [ ] first week of launch content drafted
- [ ] producer spotlight content template reviewed
- [ ] customer waitlist CTA reviewed

## 10. Data Migration Checklist

- [ ] local database backup/export process documented
- [ ] production database import process documented
- [ ] sample migration tested if possible
- [ ] sensitive data handling noted
- [ ] rollback plan documented
- [ ] SQLite production risk reviewed
- [ ] PostgreSQL migration timing decided
- [ ] exported CSV/Excel files storage policy defined

## 11. Final Pilot Readiness Checklist

- [ ] full demo flow tested
- [ ] customer order simulation completed
- [ ] Stripe payment simulation completed
- [ ] route simulation completed
- [ ] driver delivery simulation completed
- [ ] admin exports verified
- [ ] first producer outreach list ready
- [ ] first customer waitlist campaign ready
- [ ] known limitations documented
- [ ] production smoke test completed on `https://farmsourcemarket.com`
- [ ] go/no-go decision recorded
- [ ] first week support plan defined
