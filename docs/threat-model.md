# Threat model (STRIDE)

## Assets
API keys, tenant data, notification content, billing state, commercial license keys.

## Boundaries & threats

| Boundary | Threat | Control |
|---|---|---|
| Device → Edge | Key extraction from APK | Public keys are scoped, cert-pinned, HMAC-signed, per-device limited |
| Device → Edge | Replay | 300 s timestamp window + Redis `SETNX` nonce |
| Edge → Gateway | Header spoofing | Private network; `X-PP-*` stripped and re-derived at the edge |
| Gateway → Bus | Message forgery | Private Redis; envelopes carry tenant + trace |
| Worker → Webhook | SSRF | DNS resolve → IP allowlist; no redirects by default |
| Agent → Tools | Prompt injection | Tool args validated against JSON Schema; results never treated as instructions |
| Stripe → Gateway | Forged webhook | `stripe-signature` verify + `stripe_events` unique index |
| Operator | Secret sprawl | OIDC in CI, no long-lived cloud creds, Docker secrets in prod |

## Assumptions we state openly
- Public API keys are extractable. Defence is scoping + signing + pinning, not secrecy.
- Redis loss is a degradation, not an outage (rate limiting fails open).
- A malicious tenant cannot starve others: rate limiting is per-tenant as well as per-key.

## Out of scope
Your reverse proxy config, your own app's auth, DoS at the network edge before TLS.

## SLSA
Level 2. Builds run on GitHub-hosted runners with provenance attestation and keyless
cosign signatures. Base images pinned by digest. Actions pinned to commit SHAs.
