# Asset Dossier — for acquirers

## What is being sold
A complete, revenue-generating SaaS with zero founder dependency.

| | |
|---|---|
| Server | 100 % AGPL-3.0, self-hostable, no proprietary runtime |
| SDKs | Apache-2.0, three platforms, wire-compatible |
| Commercial layer | Stripe subscriptions **and** $15k/$25k buy-outs, fully automated |
| Infrastructure | `docker compose up` on any $6 VPS. No managed services required |
| Bus factor | 1 for code review, 0 for operation |

## Why there is no founder in the loop

| Function | Automation |
|---|---|
| Signup | API key minted via `POST /v1/keys`; no form |
| Onboarding | README + `make up` + two-line SDK |
| Payment | Headless Stripe Checkout; webhook upgrades the key in Mongo |
| Tier enforcement | `EntitlementService` reads a versioned, invalidatable cache |
| Upgrade prompt | `429` body field **and** `X-PP-Upgrade-Url` header |
| Overage billing | Local `usage_ledger` → Stripe Meters |
| Enterprise close | `/v1/license/tiers` + `/v1/license/quote` + Stripe one-time |
| Agreement | Generated from template on payment, stored on the license document |
| Private repo access | GitHub App invite; `status: pending` flag for follow-up |
| Support | `SUPPORT.md` SLAs; no live chat required |
| Ops | Runbook covers every P1 with copy-pasteable commands |

## Revenue model

1. **Subscriptions** — Free 1 000/mo → Pro $19 → Team $99 → metered overage.
2. **Commercial buy-out** — $15k (single product) / $25k (unlimited + OEM). Perpetual.
3. **Renewals** — $3k / $5k annually for continued updates.
4. **Marketplace** — 30 % take on third-party trigger packs (post-1.0).
5. **Enterprise self-host license** — for AGPL-averse buyers.

## Unit economics

- Marginal cost per 1 000 pulses: ≈ $0 (Redis Streams, one Mongo write, on-device TTS).
- Cloud TTS is the only variable cost, and only on Pro+ with server TTS enabled.
- Infra floor: one 2 vCPU / 4 GB VPS serves ≈ 2 000 rps of `/signal`.
- Gross margin at Pro: > 95 %. At Team: > 98 %.

## Tech moat

- At-least-once delivery with a proven no-duplicate invariant, chaos-tested nightly.
- Deterministic replay of agent runs from recorded tool I/O.
- Battery governor with a measured < 1 %/hr idle budget.
- Coalescing engine — the perceived-quality differentiator competitors will clone.
- AGPL boundary that converts enterprise forks into invoices.

## Due-diligence answers, pre-written

- **Is anything licensed non-commercially?** No. AGPL + Apache-2.0 + our own commercial terms.
- **Can it run without AWS?** Yes. Any Docker host. `BUS_DRIVER=memory` for a single box.
- **Single point of failure in code?** No. All state is in Mongo/Redis; every service is stateless.
- **What breaks if the founder disappears?** Nothing in production. `GOVERNANCE.md` names successors.
- **What is the transferable IP?** The engine, the SDKs, the trigger taxonomy, the brand.
- **What needs a human on day 1 of ownership?** Merging PRs. That is the entire list.
- **Recurring infra cost?** One VPS. Mongo and Redis are self-hosted containers.

## Post-acquisition 90-day plan

| Week | Action |
|---|---|
| 1 | Rotate `SECRET_KEY`, Stripe keys, `LICENSE_SIGNING_SECRET`; transfer DNS |
| 2 | Re-run the restore drill; confirm backups land somewhere you own |
| 3 | Turn on the marketplace waitlist; publish three first-party trigger packs |
| 4 | Raise Pro to $29 with a grandfathered cohort; measure churn |
| 6 | Launch the iOS SDK from the same wire protocol |
| 8 | Add a self-serve annual plan (2 months free) to lift LTV |
| 12 | Open the marketplace at 70/30 and onboard five tool authors |

## Known growth levers, ranked

1. **Trigger pack library** (e-commerce, fitness, fintech) — pure margin.
2. **iOS + Web SDKs** — 3× addressable market, same protocol.
3. **Managed cloud tier** — the only thing people actually want to buy.
4. **Marketplace revenue share** — compounding supply-side lock-in.
5. **Compliance add-ons** — SOC 2 report, DPA, EU residency, audit export.

## Handover artefacts

| Artefact | Location |
|---|---|
| Architecture + diagrams | `docs/architecture.md` |
| Every irreversible decision | `docs/adr/` |
| Threat model | `docs/threat-model.md` |
| Operations | `docs/runbook.md` |
| Governance + succession | `GOVERNANCE.md` |
| Support tiers + LTS | `SUPPORT.md` |
| License boundary | `docs/agpl-compliance.md`, `LICENSE.commercial` |
| Release process | `.github/workflows/release.yml` |
