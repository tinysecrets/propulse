# Contributing

## Setup

```bash
git clone https://github.com/tinysecrets/propulse && cd propulse
make dev          # compose with hot reload, local mongo + redis
make test         # unit + integration
make lint         # ruff, mypy --strict, reuse lint, boundary checks
pre-commit install
```

Requires Docker and `uv`. Nothing else. No cloud account, no API keys.

## Ground rules

1. **Zero-cost defaults are sacred.** A new required env var without a working local
   default is a bug. `scripts/check_env_defaults.py` enforces this.
2. **The two-line SDK promise.** Any SDK change that makes integration longer needs an ADR.
3. **License boundaries are hard walls.** `propulse-core` is AGPL-3.0-or-later.
   `propulse-pro` is commercial and may import core only through the narrow published
   surface. SDKs are Apache-2.0 and must not import either.
4. **No new always-on infrastructure.** Mongo and Redis only, both swappable.
5. **Additive API changes by default.** Breaking `/v1` needs an ADR and a deprecation window.

## Commit convention

Conventional Commits — `release-please` derives versions and the changelog.

