# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wire protocol. Frozen Structs -> msgspec is 3-5x faster than pydantic here."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any, Literal

import msgspec
import ulid

PROTOCOL_VERSION = 3
PROTOCOL_MIN_SUPPORTED = 1
EVENT_SPEC = "propulse.event/v1"


def new_ulid() -> str:
    # Monotonic-ish, lexicographically sortable, collision-resistant.
    return str(ulid.monotonic.new())


def dedupe_key(*parts: str, bucket_seconds: int = 60) -> str:
    bucket = int(time.time() // bucket_seconds)
    return ":".join((*parts, str(bucket)))


class TriggerKind(StrEnum):
    TIME = "time"
    SIGNAL = "signal"
    DEVICE_STATE = "device_state"
    COMPOUND = "compound"


class EventEnvelope(msgspec.Struct, frozen=True, omit_defaults=True):
    spec: str = EVENT_SPEC
    id: str = msgspec.field(default_factory=new_ulid)
    type: str = ""
    tenant_id: str = ""
    pulse_id: str = ""
    device_id: str = ""
    occurred_at: float = msgspec.field(default_factory=time.time)
    dedupe_key: str = ""
    trace_id: str = ""
    schema_ver: int = 1
    payload: dict[str, Any] = msgspec.field(default_factory=dict)


class SignalRequest(msgspec.Struct, omit_defaults=True):
    pulse: str
    install_id: str
    trigger: dict[str, Any] = msgspec.field(default_factory=dict)
    device_state: dict[str, Any] = msgspec.field(default_factory=dict)
    client_ts: float = 0.0


class SignalResponse(msgspec.Struct, omit_defaults=True):
    accepted: bool
    pulse_run_id: str = ""
    state: str = ""
    next_poll_in: int = 300
    upgrade_url: str = ""
    quota: dict[str, Any] = msgspec.field(default_factory=dict)


class DeviceRegisterRequest(msgspec.Struct, omit_defaults=True):
    install_id: str
    platform: Literal["android", "ios", "web", "server"]
    app_version: str = ""
    sdk_version: str = ""
    push_token: str = ""
    attestation: str = ""
    locale: str = "en"
    timezone: str = "UTC"


class DeviceRegisterResponse(msgspec.Struct, omit_defaults=True):
    device_id: str
    server_time: float
    next_poll_in: int = 900
    protocol_version: int = PROTOCOL_VERSION
    flags: dict[str, bool] = msgspec.field(default_factory=dict)


class AckRequest(msgspec.Struct, omit_defaults=True):
    run_id: str
    delivered_at: float = 0.0
    channel: str = "push"


ENCODER = msgspec.json.Encoder()
DECODER = msgspec.json.Decoder(EventEnvelope)
