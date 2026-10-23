# ADR 0001: Record decisions as architecture decision records

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

ProPulse combines a server, workers, scheduler, mobile SDKs, billing boundaries, and deployment automation. Unrecorded design changes make the implementation difficult to audit and can create incompatible assumptions across components.

## Decision

Record decisions that affect architecture, security, licensing, compatibility, cost, or operations in numbered files under `docs/adr/`. Accepted records are immutable; later changes supersede them with a new ADR. Implementation and release changes should reference the relevant ADR.

## Consequences

The rationale and reversal cost remain reviewable. Contributors must add an ADR when a change breaks the SDK integration promise, changes API compatibility, crosses a license boundary, or introduces always-on infrastructure. Small implementation details do not require an ADR.
