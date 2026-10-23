# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import time
from typing import Any, cast

import httpx

from propulse_sdk.sign import new_nonce, sign

VERSION = "1.0.0"
PROTOCOL_VERSION = 3


class ProPulseError(Exception):
    def __init__(
        self, message: str, status: int = 0, code: str = "error", body: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.body = body or {}


class QuotaExceeded(ProPulseError):
    def __init__(self, message: str, upgrade_url: str, limit: int, used: int) -> None:
        super().__init__(message, 429, "quota_exceeded")
        self.upgrade_url = upgrade_url
        self.limit = limit
        self.used = used


class ProPulse:
    """Two lines: ProPulse(key=..., secret=...) then .signal(...)"""

    def __init__(
        self,
        key: str,
        secret: str = "",
        base_url: str = "https://api.propulse.wah-lah.com",
        timeout: float = 15.0,
    ) -> None:
        if not key:
            raise ProPulseError("key is required", 0, "config")
        self._key = key
        self._secret = secret
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout, headers={"user-agent": f"wah-lah-propulse-py/{VERSION}"}
        )

    def __enter__(self) -> ProPulse:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def signal(
        self,
        pulse: str,
        install_id: str = "server",
        trigger: dict[str, Any] | None = None,
        device_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/pulses:signal",
            {
                "pulse": pulse,
                "install_id": install_id,
                "trigger": trigger or {"kind": "signal", "key": pulse},
                "device_state": device_state or {},
                "client_ts": time.time(),
            },
        )

    def register_device(self, install_id: str, platform: str = "server") -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/devices/register",
            {
                "install_id": install_id,
                "platform": platform,
                "sdk_version": VERSION,
            },
        )

    def ack(self, run_id: str, channel: str = "server") -> dict[str, Any]:
        return self._request("POST", "/v1/pulses/ack", {"run_id": run_id, "channel": channel})

    def create_pulse(
        self,
        key: str,
        trigger: dict[str, Any],
        action: dict[str, Any] | None = None,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/pulses",
            {
                "key": key,
                "trigger": trigger,
                "action": action or {},
                "policy": policy or {},
            },
        )

    def entitlements(self) -> dict[str, Any]:
        return self._request("GET", "/v1/billing/entitlements")

    def upgrade_url(self, plan: str = "pro") -> str:
        return cast(str, self._request("POST", "/v1/billing/checkout", {"plan": plan})["url"])

    def source_disclosure(self) -> dict[str, Any]:
        return self._request("GET", "/source")

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
        ts = str(int(time.time()))
        nonce = new_nonce()
        headers = {
            "x-pp-key": self._key,
            "x-pp-ts": ts,
            "x-pp-nonce": nonce,
            "x-pp-protocol": str(PROTOCOL_VERSION),
            "idempotency-key": f"{method}:{path}:{ts}:{nonce}",
        }
        if body:
            headers["content-type"] = "application/json"
        if self._secret:
            headers["x-pp-sig"] = sign(self._secret, ts, nonce, body)

        resp = self._client.request(
            method, self._base + path, content=body or None, headers=headers
        )
        parsed: dict[str, Any] = cast(dict[str, Any], resp.json() if resp.content else {})

        if resp.status_code == 429 and parsed.get("upgrade_url"):
            raise QuotaExceeded(
                parsed.get("detail", "quota exceeded"),
                parsed["upgrade_url"],
                parsed.get("limit", 0),
                parsed.get("used", 0),
            )
        if resp.status_code >= 400:
            raise ProPulseError(
                parsed.get("detail", resp.reason_phrase),
                resp.status_code,
                parsed.get("title", "error"),
                parsed,
            )
        return parsed
