# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.ratelimit.tokens import TokenBucket, route_cost


def test_route_cost_is_weighted():
    assert route_cost("/v1/pulses:signal") == 1
    assert route_cost("/v1/agents/run") == 25
    assert route_cost("/v1/exports") == 100


def test_route_cost_prefix_match():
    assert route_cost("/v1/pulses/abc/ack") >= 1


def test_unknown_route_is_cheap():
    assert route_cost("/v1/unknown") == 1


async def test_local_fallback_enforces_burst():
    bucket = TokenBucket(None, fail_open=True)
    results = [await bucket.consume("k", rate_per_sec=1.0, burst=3) for _ in range(5)]
    assert sum(1 for r in results if r.allowed) == 3
    assert results[-1].retry_after_ms > 0


async def test_cost_weighting_consumes_faster():
    bucket = TokenBucket(None)
    heavy = await bucket.consume("k", rate_per_sec=1.0, burst=10, cost=8)
    assert heavy.allowed
    assert heavy.remaining == 2
