# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time

from fastapi import APIRouter
from propulse_api.deps import Auth, Redis, Store
from propulse_api.schemas import DeviceRegisterBody
from propulse_core.protocol import PROTOCOL_VERSION, DeviceRegisterResponse

router = APIRouter(prefix="/v1/devices", tags=["devices"])


@router.post("/register", response_model=None)
async def register(
    payload: DeviceRegisterBody, principal: Auth, store: Store, redis: Redis
) -> DeviceRegisterResponse:
    principal.require("device:register")

    device_id = await store.upsert_device(
        {
            "tenant_id": principal.tenant_id,
            "install_id": payload.install_id,
            "platform": payload.platform,
            "app_version": payload.app_version,
            "sdk_version": payload.sdk_version,
            "push_token": payload.push_token,
            "attestation": payload.attestation,
            "locale": payload.locale,
            "timezone": payload.timezone,
            "backoff_s": 300,
        }
    )

    flags: dict[str, bool] = {}
    if redis is not None:
        try:
            import orjson

            raw = await redis.get("pp:flags")
            flags = orjson.loads(raw) if raw else {}
        except Exception:
            flags = {}

    return DeviceRegisterResponse(
        device_id=device_id,
        server_time=time.time(),
        next_poll_in=900,
        protocol_version=PROTOCOL_VERSION,
        flags=flags,
    )


@router.get("", summary="List devices")
async def list_devices(principal: Auth, store: Store) -> dict[str, object]:
    devices = await store.list_devices(principal.tenant_id)
    return {"data": [{"id": str(d.pop("_id", "")), **d} for d in devices]}
