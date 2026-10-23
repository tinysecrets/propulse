# Deprecation policy

| Surface | Minimum notice | Announced via |
|---|---|---|
| `/v1` route | 12 months | `Deprecation` + `Sunset` headers, CHANGELOG, docs |
| Response field | 12 months | docs + OpenAPI `deprecated: true` |
| SDK major | 6 months | SDK CHANGELOG, in-app warning, release notes |
| Wire protocol version | 24 months | `X-PP-Protocol` negotiation + docs |
| Driver / adapter | 6 months | startup warning log |

## Process
1. Mark deprecated in code and OpenAPI.
2. Emit headers. Log a counter per deprecated route.
3. Announce in CHANGELOG under **Deprecations**.
4. After the window, remove in the next major.
5. Never remove in a patch or minor.
