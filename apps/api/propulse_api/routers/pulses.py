# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query, Request
from propulse_core.domain.states import PulseState
from propulse_core.errors import NotFoundError, QuotaExceeded
from propulse_core.protocol import (
    EventEnvelope,
    SignalResponse,
    dedupe_key,
)

from propulse_api.deps import Auth, Billing, Bus, Entitlements, Store, TraceId
from propulse_api.schemas import AckBody, SignalBody

router = APIRouter(prefix="/v1/pulses", tags=["pulses"])

NEXT_POLL_DEFAULT = 300
NEXT_POLL_MIN = 60
NEXT_POLL_MAX = 900


def _next_poll(priority: str) -> int:
    return {
        "urgent": NEXT_POLL_MIN,
        "high": 120,
        "normal": NEXT_POLL_DEFAULT,
        "low": NEXT_POLL_MAX,
    }.get(priority, NEXT_POLL_DEFAULT)


@router.post(":signal", response_model=None, summary="Device reports a trigger fired")
async def signal(
    request: Request,
    payload: SignalBody,
    principal: Auth,
    store: Store,
    bus: Bus,
    entitlements: Entitlements,
    billing: Billing,
    trace_id: TraceId,
) -> SignalResponse:
    principal.require("pulse:signal")

    pulse = await store.find_pulse(principal.tenant_id, payload.pulse)
    if pulse is None:
        raise NotFoundError(f"pulse {payload.pulse!r} is not registered", pulse=payload.pulse)

    device = await store.get_device(principal.tenant_id, payload.install_id)
    device_id = str(device["_id"]) if device else ""

    try:
        ent = await entitlements.consume_pulse(principal.tenant_id)
        upgrade_url = ""
    except QuotaExceeded as exc:
        if not pulse.get("overage_ok", True):
            raise
        ent = await entitlements.resolve(principal.tenant_id)
        upgrade_url = exc.upgrade_url

    now = time.time()
    dkey = dedupe_key(
        str(pulse["_id"]),
        payload.install_id,
        bucket_seconds=int(pulse.get("policy", {}).get("dedupe_window_seconds", 900)),
    )

    run_id = await store.create_run(
        {
            "tenant_id": principal.tenant_id,
            "pulse_id": str(pulse["_id"]),
            "pulse_key": payload.pulse,
            "device_id": device_id,
            "install_id": payload.install_id,
            "state": PulseState.COALESCING.value,
            "dedupe_key": dkey,
            "trace_id": trace_id,
            "attempts": 0,
            "lease_owner": None,
            "lease_at": None,
            "tool_io": [],
            "trigger": payload.trigger,
            "device_state": payload.device_state,
            "created_at": now,
        }
    )

    evt = EventEnvelope(
        type="pulse.triggered",
        tenant_id=principal.tenant_id,
        pulse_id=str(pulse["_id"]),
        device_id=device_id,
        dedupe_key=dkey,
        trace_id=trace_id,
        payload={
            "run_id": run_id,
            "install_id": payload.install_id,
            "trigger": payload.trigger,
            "device_state": payload.device_state,
            "pulse_key": payload.pulse,
        },
    )
    await bus.publish("pp:pulse.triggered", evt)
    await store.emit_event(
        {
            "meta": {"tenant_id": principal.tenant_id, "type": "signal"},
            "type": "pulse.triggered",
            "trace_id": trace_id,
            "payload": {"pulse_key": payload.pulse},
        }
    )

    return SignalResponse(
        accepted=True,
        pulse_run_id=run_id,
        state=PulseState.COALESCING.value,
        next_poll_in=_next_poll(pulse.get("policy", {}).get("priority", "normal")),
        upgrade_url=upgrade_url,
        quota={
            "limit": ent.monthly_limit,
            "used": ent.used,
            "remaining": ent.remaining,
            "plan": ent.plan.id,
        },
    )


@router.post("/ack", response_model=None, summary="Delivery receipt")
async def ack(payload: AckBody, principal: Auth, store: Store) -> dict[str, object]:
    principal.require("pulse:ack")
    run = await store.get_run(payload.run_id)
    if run is None:
        raise NotFoundError("run not found", run_id=payload.run_id)

    transitioned = await store.transition_run(
        payload.run_id,
        [PulseState.NOTIFYING.value, PulseState.EXECUTING.value],
        {
            "state": PulseState.COMPLETED.value,
            "completed_at": time.time(),
            "delivered_at": payload.delivered_at or time.time(),
            "channel": payload.channel,
        },
    )
    await store.col("notifications").insert_one(
        {
            "run_id": payload.run_id,
            "tenant_id": principal.tenant_id,
            "channel": payload.channel,
            "ack_at": time.time(),
        }
    )
    return {"ok": True, "transitioned": transitioned}


@router.get("", summary="List pulses")
async def list_pulses(
    principal: Auth, store: Store, state: str | None = None, limit: int = Query(50, ge=1, le=100)
) -> dict[str, object]:
    pulses = await store.list_pulses(principal.tenant_id, state=state, limit=limit)
    return {"data": [_ser(p) for p in pulses], "count": len(pulses)}


@router.post("", status_code=201, summary="Register a pulse")
async def create_pulse(
    request: Request, principal: Auth, store: Store, entitlements: Entitlements
) -> dict[str, object]:
    principal.require("pulse:write")
    body = await request.json()

    if body.get("trigger", {}).get("kind") == "compound":
        await entitlements.require_feature(principal.tenant_id, "compound_triggers")

    pulse_id = await store.create_pulse(
        {
            "tenant_id": principal.tenant_id,
            "key": body["key"],
            "name": body.get("name", body["key"]),
            "trigger": body.get("trigger", {}),
            "action": body.get("action", {"kind": "say", "text": body.get("name", body["key"])}),
            "policy": body.get("policy", {}),
            "state": PulseState.REGISTERED.value,
            "next_fire_at": time.time(),
            "schema_ver": 1,
            "revision": 1,
        }
    )
    return {"id": pulse_id, "state": PulseState.REGISTERED.value}


@router.get("/runs", summary="List recent runs")
async def list_runs(
    principal: Auth, store: Store, limit: int = Query(50, ge=1, le=100)
) -> dict[str, object]:
    runs = await store.list_runs(principal.tenant_id, limit=limit)
    return {"data": [_ser(r) for r in runs], "count": len(runs)}


def _ser(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["id"] = str(out.pop("_id", ""))
    return out
