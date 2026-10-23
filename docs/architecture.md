# Architecture

## Components

- **Core library:** protocol envelope, state machine, key and HMAC helpers, rate limiting, entitlement logic, licensing checks, and adapters.
- **API gateway:** FastAPI routes for health, device registration, pulse operations, keys, billing, licensing, and source disclosure.
- **Worker:** consumes work from the configured bus, evaluates agent budgets, coalesces voice output, and sends outbound webhooks through SSRF guards.
- **Scheduler:** coordinates scheduled ticks and reaps orphaned leases.
- **Storage and bus:** MongoDB for durable application state and Redis Streams for distributed work; an in-memory bus is available for tests/local use.
- **SDKs:** Android, JavaScript/TypeScript, and Python clients sign requests using the protocol defined by the core package.

## Request flow

1. A client sends a signed signal to the API.
2. Middleware validates request timing, nonce, protocol version, idempotency, and tenant limits.
3. The API persists the request and publishes work.
4. Workers evaluate policy and produce an outcome.
5. A client acknowledges delivery or polls for the next action.

## Security boundaries

Request authentication, nonce freshness, idempotency, rate limits, webhook egress controls, and licensing checks are enforced in server code. See the [threat model](threat-model.md). Production secret management, network policy, and operational access controls must still be configured for the target environment.
