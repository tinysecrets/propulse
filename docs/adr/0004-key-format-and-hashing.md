# ADR 0004: Use distinct public and secret API-key formats

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

Public client keys may be embedded in application packages and must be verifiable on every request. Secret keys must remain server-side and should be resistant to offline guessing if a credential store is exposed.

## Decision

Use visibly distinct `pp_pub_` and `pp_sec_` prefixes. Store public-key digests with SHA-256 for fast verification; store secret-key verifiers with Argon2id. Scope each key by allowed capabilities, never log plaintext keys, and use request HMAC signatures with timestamp and nonce validation for replay resistance. Public keys are not treated as confidential credentials.

## Consequences

Key rotation, scope ceilings, rate limits, and request signing remain part of the security model. Any key-format change requires a compatibility plan and tests for malformed, tampered, and wrong-secret cases.
