# 5. Headless billing — no dashboard

- Status: accepted
- Date: 2026-10-23

## Context
A billing dashboard is a second product: auth, sessions, SSR, styling, a support surface.
Every hour on it is an hour not spent on the engine.

## Decision
Stripe Checkout and the Stripe Customer Portal do the UI. Our surface is four endpoints:

- `GET /v1/billing/plans` — public catalogue
- `POST /v1/billing/checkout` — returns a URL
- `POST /v1/billing/portal` — returns a URL
- `POST /v1/billing/webhook` — upgrades the key

The upgrade prompt is a `429` carrying `upgrade_url` in the body and `X-PP-Upgrade-Url`
in the headers.

## Consequences
- Zero frontend to maintain. Stripe owns PCI, tax, 3DS, invoices, dunning.
- Conversion happens inside the developer's own CLI or app — no context switch.
- `BILLING_DRIVER=null` means a full product with no Stripe account at all.
- A marketing site is optional, not load-bearing.

## Alternatives
- Custom dashboard: control, cost, time.
- Stripe Pricing Table embed: still a page, less control over the funnel.
- Paddle / LemonSqueezy: viable merchant-of-record; Stripe's API is better and the
  `BillingAdapter` protocol lets us swap.

## Reversal cost
Low. A dashboard can be added later without touching the engine.
