# Governance

## Model
Benevolent-maintainer with a technical steering group. One person (the BDFL) has final say
on licensing and the open-core boundary; everything else is consensus.

## Roles

| Role | Grants | Expectation |
|---|---|---|
| Contributor | PRs | signed CLA |
| Reviewer | approve PRs in a path via CODEOWNERS | 3 business days response |
| Maintainer | merge, release, triage, branch admin | sustained, 6+ months |
| Steering | ADRs, roadmap, license boundary, Pro boundary | quarterly sync |

Promotion by nomination from two maintainers plus no objections for 7 days.
Inactivity over 6 months → emeritus; access retained.

## Succession (no-founder-dependency clause)
If the BDFL is unavailable for 30 consecutive days, steering gains full authority over
releases and the license boundary. If unreachable for 90 days, steering may relicense
within the constraints of `LICENSE` and `CLA.md`.

## Decision records
Every irreversible or expensive-to-reverse decision needs an ADR merged *before* the
implementing code. ADRs are immutable once accepted; supersede rather than edit.

## Conflict resolution
Discuss in the issue → write an ADR → steering vote. Simple majority; BDFL breaks ties.

## Open-core boundary
Changing what is AGPL versus commercial requires an ADR with stated rationale.
Default rule: if a feature is needed to self-host usefully, it belongs in core.

## LTS
Every minor release line receives security fixes for 12 months on `release/x.y`.

## Trademark
Owned by the project, licensed per `TRADEMARK.md`, never transferred by a code fork.
