# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Annotated, Any, Literal

import msgspec


class TimeTrigger(msgspec.Struct, tag="time", omit_defaults=True):
    at: float | None = None
    every_seconds: int | None = None
    window_start_hour: int | None = None
    window_end_hour: int | None = None


class SignalTrigger(msgspec.Struct, tag="signal", omit_defaults=True):
    key: str
    threshold: int = 1


class DeviceStateTrigger(msgspec.Struct, tag="device_state", omit_defaults=True):
    battery_below: int | None = None
    charging: bool | None = None
    network: Literal["any", "wifi", "cellular", "none"] = "any"
    screen_on: bool | None = None
    geofence: dict[str, float] | None = None


class CompoundTrigger(msgspec.Struct, tag="compound", omit_defaults=True):
    """Pro tier. N-of-M over a sliding window."""

    op: Literal["and", "or", "n_of_m"]
    n: int = 2
    window_seconds: int = 600
    children: list[dict[str, Any]] = msgspec.field(default_factory=list)


Trigger = Annotated[
    TimeTrigger | SignalTrigger | DeviceStateTrigger | CompoundTrigger,
    msgspec.field(tag_field="kind"),
]


class SayAction(msgspec.Struct, tag="say", omit_defaults=True):
    text: str
    voice: str = "default"
    rate: float = 1.0
    interrupt: bool = False


class OpenDeepLinkAction(msgspec.Struct, tag="open", omit_defaults=True):
    uri: str
    title: str = ""
    body: str = ""


class CallWebhookAction(msgspec.Struct, tag="webhook", omit_defaults=True):
    url: str
    method: Literal["POST", "PUT", "PATCH"] = "POST"
    headers: dict[str, str] = msgspec.field(default_factory=dict)
    body_template: str = "{{payload}}"


class RunAgentAction(msgspec.Struct, tag="agent", omit_defaults=True):
    goal: str
    tools: list[str] = msgspec.field(default_factory=list)
    budget_ms: int = 8000
    budget_credits: int = 50


Action = Annotated[
    SayAction | OpenDeepLinkAction | CallWebhookAction | RunAgentAction,
    msgspec.field(tag_field="kind"),
]


class PulsePolicy(msgspec.Struct, omit_defaults=True):
    ttl_seconds: int = 3600
    dedupe_window_seconds: int = 900
    coalesce_window_seconds: int = 20
    max_per_day: int = 5
    quiet_hours_start: int | None = 23
    quiet_hours_end: int | None = 7
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    budget_ms: int = 8000
    budget_credits: int = 50


class PulseSpec(msgspec.Struct, omit_defaults=True):
    id: str = ""
    tenant_id: str = ""
    key: str = ""
    name: str = ""
    trigger: dict[str, Any] = msgspec.field(default_factory=dict)
    action: dict[str, Any] = msgspec.field(default_factory=dict)
    policy: PulsePolicy = msgspec.field(default_factory=PulsePolicy)
    state: str = "registered"
    schema_ver: int = 1
    revision: int = 1
    created_at: float = 0.0
    updated_at: float = 0.0
