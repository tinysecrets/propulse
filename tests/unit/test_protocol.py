# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.protocol import (
    DECODER,
    ENCODER,
    PROTOCOL_MIN_SUPPORTED,
    PROTOCOL_VERSION,
    EventEnvelope,
    dedupe_key,
    new_ulid,
)


def test_ulids_are_unique_and_sortable():
    ids = [new_ulid() for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert ids == sorted(ids)


def test_envelope_roundtrip():
    evt = EventEnvelope(type="pulse.triggered", tenant_id="t1", payload={"a": 1})
    decoded = DECODER.decode(ENCODER.encode(evt))
    assert decoded.tenant_id == "t1"
    assert decoded.payload == {"a": 1}
    assert decoded.spec == "propulse.event/v1"


def test_envelope_has_defaults():
    evt = EventEnvelope(type="x")
    assert evt.id
    assert evt.occurred_at
    assert evt.schema_ver == 1


def test_dedupe_key_buckets():
    a = dedupe_key("p1", "d1", bucket_seconds=900)
    b = dedupe_key("p1", "d1", bucket_seconds=900)
    assert a == b
    assert a.startswith("p1:d1:")


def test_protocol_window_is_two_behind():
    assert PROTOCOL_VERSION - PROTOCOL_MIN_SUPPORTED == 2
