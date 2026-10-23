# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pydantic request models at the HTTP boundary; core wire structs remain msgspec."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceRegisterBody(BaseModel):
    install_id: str
    platform: Literal["android", "ios", "web", "server"]
    app_version: str = ""
    sdk_version: str = ""
    push_token: str = ""
    attestation: str = ""
    locale: str = "en"
    timezone: str = "UTC"


class SignalBody(BaseModel):
    pulse: str
    install_id: str
    trigger: dict[str, Any] = Field(default_factory=dict)
    device_state: dict[str, Any] = Field(default_factory=dict)
    client_ts: float = 0.0


class AckBody(BaseModel):
    run_id: str
    delivered_at: float = 0.0
    channel: str = "push"
