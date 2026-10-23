# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operator CLI. Zero cloud credentials needed for any command."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Iterable
from typing import Any, Literal, cast

from propulse_core.security.keys import mint_key, new_signing_secret


def _app() -> Any:
    from propulse_api.app import create_app

    return create_app()


async def _store() -> Any:
    from propulse_core.storage.mongo import MongoStore

    from propulse_api.settings import settings

    store = MongoStore(settings.mongo_uri, settings.mongo_db)
    await store.connect()
    return store


# --- migrate ---------------------------------------------------------------
async def cmd_migrate() -> int:
    store = await _store()
    await store.ensure_indexes()
    await store.upsert_tenant(
        {"_id": "demo", "slug": "demo", "name": "Demo Tenant", "plan": "free"}
    )
    await store.upsert_entitlements(
        "demo",
        {"plan": "free", "features": ["on_device_tts", "basic_triggers"], "monthly_limit": 1000},
    )
    await store.close()
    print("migrations applied")
    return 0


# --- seed ------------------------------------------------------------------
async def cmd_seed() -> int:
    store = await _store()
    tenant_id = "demo"

    existing = [k async for k in _aiter(store.list_api_keys(tenant_id))]
    if not existing:
        pub = mint_key("pub", "test")
        sec = mint_key("sec", "test")
        for minted in (pub, sec):
            await store.create_api_key(
                {
                    "tenant_id": tenant_id,
                    "key_id": minted.key_id,
                    "kind": minted.kind,
                    "name": f"demo {minted.kind}",
                    "hash": minted.digest,
                    "signing_secret": new_signing_secret() if minted.kind == "pub" else "",
                    "scopes": ["pulse:signal", "device:register", "pulse:ack", "config:read"]
                    + (
                        ["pulse:write", "key:write", "billing:read"] if minted.kind == "sec" else []
                    ),
                    "plan": "free",
                    "active": True,
                }
            )
        print("\n  demo keys (store them now)\n")
        print(f"  PP_PUB_KEY={pub.plaintext}")
        print(f"  PP_SEC_KEY={sec.plaintext}\n")

    if not await store.find_pulse(tenant_id, "cart_idle"):
        await store.create_pulse(
            {
                "tenant_id": tenant_id,
                "key": "cart_idle",
                "name": "Cart idle nudge",
                "trigger": {"kind": "time", "every_seconds": 900},
                "action": {"kind": "say", "text": "Still thinking? Here is 10 percent off."},
                "policy": {"ttl_seconds": 3600, "dedupe_window_seconds": 900, "priority": "normal"},
                "state": "armed",
                "next_fire_at": time.time(),
                "schema_ver": 1,
                "revision": 1,
            }
        )
        print("  seeded pulse: cart_idle")

    await store.close()
    return 0


async def _aiter(coro: Awaitable[Iterable[dict[str, Any]]]) -> AsyncIterator[dict[str, Any]]:
    for item in await coro:
        yield item


# --- demo ------------------------------------------------------------------
async def cmd_demo() -> int:
    from propulse_core.domain.states import PulseState
    from propulse_core.protocol import EventEnvelope

    store = await _store()
    from propulse_core.bus.factory import make_bus
    from propulse_core.entitlements import EntitlementService
    from propulse_core.errors import QuotaExceeded

    from propulse_api.settings import settings

    bus = make_bus(settings.bus_driver, settings.redis_url)
    entitlements = EntitlementService(store, None, upgrade_url=settings.upgrade_url)

    try:
        ent = await entitlements.consume_pulse("demo")
        print(f"  quota: {ent.used}/{ent.monthly_limit} ({ent.plan.name})")
    except QuotaExceeded as exc:
        print(f"  QUOTA EXCEEDED -> upgrade at {exc.upgrade_url}")

    now = time.time()
    run_id = await store.create_run(
        {
            "tenant_id": "demo",
            "pulse_key": "cart_idle",
            "pulse_id": "demo",
            "device_id": "",
            "install_id": "ins_demo",
            "state": PulseState.COALESCING.value,
            "dedupe_key": f"demo:ins_demo:{int(now // 900)}",
            "trace_id": "demo",
            "attempts": 0,
            "lease_owner": None,
            "lease_at": None,
            "tool_io": [],
            "trigger": {},
            "device_state": {},
            "created_at": now,
        }
    )
    await bus.publish(
        "pp:pulse.triggered",
        EventEnvelope(
            type="pulse.triggered",
            tenant_id="demo",
            pulse_id="demo",
            trace_id="demo",
            payload={"run_id": run_id, "pulse_key": "cart_idle"},
        ),
    )
    print(f"  run created: {run_id}")
    print("  published pulse.triggered -> start the worker to see it complete")
    await bus.close()
    await store.close()
    return 0


# --- doctor ----------------------------------------------------------------
async def cmd_doctor() -> int:
    from propulse_api.settings import settings

    report: dict[str, Any] = {
        "version": __import__("propulse_core").__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "env": settings.env,
        "drivers": {
            "bus": settings.bus_driver,
            "billing": settings.billing_driver,
            "llm": settings.llm_driver,
            "tts": settings.tts_driver,
            "storage": settings.storage_driver,
        },
        "checks": {},
    }
    try:
        store = await _store()
        report["checks"]["mongo"] = await store.ping()
        await store.close()
    except Exception as exc:
        report["checks"]["mongo"] = f"FAIL: {exc}"

    try:
        from redis.asyncio import Redis

        r = Redis.from_url(settings.redis_url)
        await r.ping()
        report["checks"]["redis"] = True
        await r.aclose()
    except Exception as exc:
        report["checks"]["redis"] = f"FAIL: {exc}"

    report["checks"]["secret_key_set"] = (
        settings.secret_key != "dev-only-change-me-in-production-32bytes"
    )
    report["checks"]["stripe_configured"] = bool(settings.stripe_secret_key)
    print(json.dumps(report, indent=2))
    return 0


# --- openapi ---------------------------------------------------------------
async def cmd_export_openapi() -> int:
    app = _app()
    print(json.dumps(app.openapi(), indent=2, sort_keys=True))
    return 0


# --- sbom ------------------------------------------------------------------
async def cmd_sbom() -> int:
    import importlib.metadata as md

    packages = sorted(
        (
            {
                "name": d.metadata["Name"],
                "version": d.version,
                "license": d.metadata.get("License", "UNKNOWN"),
            }
            for d in md.distributions()
            if d.metadata.get("Name")
        ),
        key=lambda p: p["name"].lower(),
    )
    print(
        json.dumps(
            {
                "spdxVersion": "SPDX-2.3",
                "name": "wah-lah-propulse",
                "dataLicense": "CC0-1.0",
                "documentNamespace": (
                    f"https://propulse.wah-lah.com/sbom/{os.getenv('GIT_SHA', 'dev')}"
                ),
                "creationInfo": {
                    "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "creators": ["Tool: propulse-cli"],
                },
                "packages": [
                    {
                        "name": p["name"],
                        "versionInfo": p["version"],
                        "licenseDeclared": p["license"],
                        "SPDXID": f"SPDXRef-{p['name']}",
                    }
                    for p in packages
                ],
            },
            indent=2,
        )
    )
    return 0


# --- key -------------------------------------------------------------------
async def cmd_key_mint(kind: str) -> int:
    minted = mint_key(cast(Literal["pub", "sec"], kind if kind in ("pub", "sec") else "pub"))
    print(
        json.dumps(
            {
                "key": minted.plaintext,
                "key_id": minted.key_id,
                "kind": minted.kind,
                "signing_secret": new_signing_secret() if minted.kind == "pub" else "",
            },
            indent=2,
        )
    )
    return 0


COMMANDS = {
    "migrate": cmd_migrate,
    "seed": cmd_seed,
    "demo": cmd_demo,
    "doctor": cmd_doctor,
    "export-openapi": cmd_export_openapi,
    "sbom": cmd_sbom,
}


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        print("usage: propulse <migrate|seed|demo|doctor|export-openapi|sbom|key-mint>")
        return 1
    cmd = args[0]
    if cmd == "key-mint":
        return asyncio.run(cmd_key_mint(args[1] if len(args) > 1 else "pub"))
    fn = COMMANDS.get(cmd)
    if fn is None:
        print(f"unknown command: {cmd}")
        return 1
    return asyncio.run(fn())


if __name__ == "__main__":
    raise SystemExit(main())
