# Wah-Lah ProPulse AI

ProPulse is a background, event-driven agent orchestrator. Applications submit signals; ProPulse evaluates triggers and policy, queues work, and returns an outcome without requiring a dashboard.

## Start locally

```bash
cp .env.example .env
make up
make demo
```

The default local profile uses MongoDB, Redis, and zero-cost adapter defaults. See the [quickstart](quickstart.md) and [operations runbook](runbook.md).

## Project map

- `packages/propulse-core`: protocol, state machine, signing, entitlement and bus abstractions.
- `apps/api`: FastAPI gateway and versioned endpoints.
- `apps/worker`: orchestration, agent execution, voice coalescing, and guarded webhook delivery.
- `apps/scheduler`: scheduled work and lease recovery.
- `packages/sdk-android`, `packages/sdk-js`, `packages/sdk-python`: client SDKs.

## Important status note

Local automated tests and SDK checks should be run before each release. Production deployment, signing/publishing credentials, and public service DNS are environment-specific and are not supplied by this source repository.
