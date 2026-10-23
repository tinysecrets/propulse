# 6. Headless AGPL enforcement via `/source`

- Status: accepted
- Date: 2026-10-23

## Context
Open-core fails in one of two ways: nobody adopts it, or everybody adopts it and nobody
pays. The second is a distribution problem, not a legal one. Enterprise legal teams
reject AGPL by reflex, and most never read section 13.

## Decision
Make compliance a ten-second `curl`, and make the alternative a ten-second purchase.

- `GET /source` returns repo, license, exact commit SHA, archive URL, and a plain-English
  `notices` block stating what you must and must not do.
- `GET /v1/license/tiers` returns the two buy-outs with prices and grants.
- `POST /v1/license/checkout` takes payment and auto-issues a perpetual, offline-verifiable
  key plus a generated agreement.
- `docs/agpl-compliance.md` leads with "you do not have to open-source your app."

## Consequences
- The legal objection becomes a one-line verification a developer can run.
- Every self-hosted deployment carries a permanent, visible upsell in its own API.
- `LICENSE.commercial` exists before the first inbound email, so deals close in days.
- Requires a CLA so we can dual-license contributions.

## Alternatives
- MIT core with a paid Pro module: weaker pull toward paying.
- BSL with a 4-year conversion: not OSI-approved, confusing to procurement.
- No commercial option: forks keep mods private, we never invoice.

## Reversal cost
High. Loosening core to permissive forfeits the buy-out funnel permanently.
