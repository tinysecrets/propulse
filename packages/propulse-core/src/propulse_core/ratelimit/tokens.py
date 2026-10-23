# SPDX-License-Identifier: AGPL-3.0-or-later
"""Atomic cost-weighted token bucket. One Redis round trip, zero races."""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis

LUA_TOKEN_BUCKET = """
local key, rate, burst, cost, now_ms =
  KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3]), tonumber(ARGV[4])
local st = redis.call('HMGET', key, 'ts', 'tokens')
local ts = tonumber(st[1]) or now_ms
local tokens = math.min(burst, (tonumber(st[2]) or burst) + (now_ms - ts) * rate / 1000)
local allowed = 0
if tokens >= cost then allowed = 1 tokens = tokens - cost end
redis.call('HSET', key, 'ts', now_ms, 'tokens', tokens)
local ttl = math.ceil(burst / rate * 1000) + 1000
redis.call('PEXPIRE', key, ttl)
local retry = 0
if allowed == 0 then retry = math.ceil((cost - tokens) / rate * 1000) end
return {allowed, math.floor(tokens), retry, ttl}
"""


@dataclass(frozen=True, slots=True)
class BucketResult:
    allowed: bool
    remaining: int
    retry_after_ms: int
    limit: int

    @property
    def reset_seconds(self) -> int:
        return max(1, self.retry_after_ms // 1000) if not self.allowed else 0


class TokenBucket:
    """Lazy-loaded Lua. Survives Redis restart; falls back in-process on outage."""

    def __init__(self, redis: Redis | None, *, fail_open: bool = True) -> None:
        self._redis = redis
        self._fail_open = fail_open
        self._sha: str | None = None
        self._local: dict[str, tuple[float, float]] = {}

    async def _load(self) -> str | None:
        if self._redis is None:
            return None
        if self._sha is None:
            try:
                self._sha = await self._redis.script_load(LUA_TOKEN_BUCKET)
            except Exception:
                return None
        return self._sha

    async def consume(
        self, key: str, *, rate_per_sec: float, burst: int, cost: int = 1
    ) -> BucketResult:
        now_ms = int(time.time() * 1000)
        sha = await self._load()
        redis_client = self._redis
        if sha is not None and redis_client is not None:
            try:
                allowed, remaining, retry, _ttl = await redis_client.evalsha(
                    sha, 1, key, rate_per_sec, burst, cost, now_ms
                )
                return BucketResult(bool(allowed), int(remaining), int(retry), burst)
            except Exception:
                if not self._fail_open:
                    raise
        return self._consume_local(
            key, rate_per_sec=rate_per_sec, burst=burst, cost=cost, now_ms=now_ms
        )

    def _consume_local(
        self, key: str, *, rate_per_sec: float, burst: int, cost: int, now_ms: int
    ) -> BucketResult:
        ts, tokens = self._local.get(key, (float(now_ms), float(burst)))
        tokens = min(burst, tokens + (now_ms - ts) * rate_per_sec / 1000)
        allowed = tokens >= cost
        if allowed:
            tokens -= cost
        self._local[key] = (float(now_ms), tokens)
        retry = 0 if allowed else int((cost - tokens) / rate_per_sec * 1000)
        return BucketResult(allowed, int(tokens), retry, burst)


ROUTE_COST: dict[str, int] = {
    "/v1/pulses:signal": 1,
    "/v1/pulses": 2,
    "/v1/devices": 2,
    "/v1/pulses/ack": 1,
    "/v1/config": 1,
    "/v1/events": 3,
    "/v1/keys": 5,
    "/v1/agents/run": 25,
    "/v1/billing/checkout": 10,
    "/v1/license/quote": 5,
    "/v1/exports": 100,
}


def route_cost(path: str) -> int:
    if path in ROUTE_COST:
        return ROUTE_COST[path]
    for prefix, cost in ROUTE_COST.items():
        if path.startswith(prefix):
            return cost
    return 1
