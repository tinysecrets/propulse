# API versioning

## Rules

1. `/v1` is stable. Breaking changes require a new major path.
2. Additive changes ship freely: new optional params, new response fields, new routes.
3. Minimum deprecation window: **12 months** for `/v1`, 6 months for SDK majors.

## Wire protocol negotiation

SDKs send `X-PP-Protocol: <n>`. The server supports `current` through `current-2` and
echoes the negotiated version in `X-PP-Protocol` on every response. Unknown higher versions
are downgraded, never rejected — this is what keeps 3-year-old installs working.

## Deprecation signalling

RFC 8594 headers on deprecated routes:

