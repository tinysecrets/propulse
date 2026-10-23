# Quickstart

## Requirements

- Docker Engine with the Compose plugin
- Git
- Python 3.12 and `uv` for local development
- Node.js 18+ for the JavaScript SDK

## Start the local stack

```bash
cp .env.example .env
make up
make doctor
make demo
```

The `.env.example` file documents supported defaults. Keep real credentials in a local, untracked `.env` file or a secret manager; never commit them.

## Verify

```bash
make test
make lint
cd packages/sdk-js
npm ci
npm test
npm run build
npm run lint
```

The local demonstration validates the configured local path; it does not establish production readiness, external billing setup, DNS, or deployment credentials.
