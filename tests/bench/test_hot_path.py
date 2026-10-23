# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.protocol import DECODER, ENCODER, EventEnvelope
from propulse_core.ratelimit.tokens import TokenBucket, route_cost
from propulse_core.security.keys import mint_key, verify_key


def test_bench_envelope_encode(benchmark):
    evt = EventEnvelope(type="pulse.triggered", tenant_id="t", payload={"a": 1, "b": [1, 2]})
    benchmark(ENCODER.encode, evt)


def test_bench_envelope_decode(benchmark):
    raw = ENCODER.encode(EventEnvelope(type="pulse.triggered", payload={"a": 1}))
    benchmark(DECODER.decode, raw)


def test_bench_public_key_verify(benchmark):
    minted = mint_key("pub")
    benchmark(lambda: verify_key(minted.plaintext, minted.digest, "pub"))


def test_bench_route_cost(benchmark):
    benchmark(route_cost, "/v1/pulses:signal")


def test_bench_local_bucket(benchmark):
    bucket = TokenBucket(None)
    benchmark(lambda: bucket._consume_local("k", rate_per_sec=60, burst=60, cost=1, now_ms=0))
