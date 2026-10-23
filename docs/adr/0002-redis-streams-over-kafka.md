# 2. Redis Streams as the default event bus

- Status: accepted
- Date: 2026-10-23
- Deciders: steering

## Context
We need at-least-once delivery, consumer groups, replay, and dead-lettering. The
constraint that dominates: `docker compose up` must boot a working stack with **zero
external services**. Kafka means KRaft or Zookeeper, a JVM, and 2 GB of RAM before the
product does anything.

## Decision
Redis Streams is the default. A `Bus` protocol with a `memory` adapter keeps tests
instant and single-box deploys trivial.

Delivery guarantees come from `XREADGROUP`, `XAUTOCLAIM`, `XACK`, `XADD` with approximate
`MAXLEN`, and idempotent handlers keyed on `dedupe_key`.

## Consequences
- Boot time under 30 s, RAM floor ~400 MB.
- At-least-once with reclaim-based crash recovery.
- Ceiling around a few hundred thousand events/minute on one Redis — enough for the
  first several thousand tenants.
- NATS/Kafka/SQS remain a future adapter, not a rewrite.

## Alternatives
- **Kafka**: best throughput and retention, worst local ergonomics.
- **NATS JetStream**: great fit, another binary, less familiar to Python devs.
- **Postgres LISTEN/NOTIFY**: adds a database dependency and weaker replay.
- **SQS**: managed cost, not offline.

## Reversal cost
Medium. The `Bus` protocol is narrow (publish/consume/ack/reclaim/dlq), so an adapter is
a few hundred lines — not a rearchitecture.
