# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time
from typing import Any, Literal, cast

from fastapi import APIRouter
from propulse_core.errors import NotFoundError
from propulse_core.security.keys import mint_key, new_signing_secret, scopes_for

from propulse_api.deps import Auth, Redis, Store

router = APIRouter(prefix="/v1/keys", tags=["keys"])

ROTATION_GRACE_SECONDS = 86_400


@router.get("", summary="List API keys (masked)")
async def list_keys(principal: Auth, store: Store) -> dict[str, object]:
    keys = await store.list_api_keys(principal.tenant_id)
    return {
        "data": [
            {
                "key_id": k["key_id"],
                "kind": k["kind"],
                "name": k.get("name", ""),
                "scopes": k.get("scopes", []),
                "active": k.get("active", True),
                "created_at": k.get("created_at"),
                "last_used_at": k.get("last_used_at"),
                "revoked_at": k.get("revoked_at"),
            }
            for k in keys
        ]
    }


@router.post("", status_code=201, summary="Mint a key (plaintext shown once)")
async def create_key(
    body: dict[str, Any],
    principal: Auth,
    store: Store,
) -> dict[str, object]:
    principal.require("key:write")
    kind = body.get("kind", "pub")
    if kind not in ("pub", "sec"):
        kind = "pub"
    minted = mint_key(
        cast(Literal["pub", "sec"], kind), env="live" if body.get("live", True) else "test"
    )
    signing_secret = new_signing_secret() if kind == "pub" else ""

    await store.create_api_key(
        {
            "tenant_id": principal.tenant_id,
            "key_id": minted.key_id,
            "kind": kind,
            "name": body.get("name", f"{kind} key"),
            "hash": minted.digest,
            "signing_secret": signing_secret,
            "scopes": sorted(scopes_for(kind, body.get("scopes"))),
            "plan": principal.plan,
            "active": True,
            "origins": body.get("origins", []),
        }
    )
    return {
        "key_id": minted.key_id,
        "key": minted.plaintext,
        "kind": kind,
        "signing_secret": signing_secret,
        "scopes": sorted(scopes_for(kind, body.get("scopes"))),
        "warning": "store the key now — it is never shown again",
    }


@router.post("/{key_id}/rotate", summary="Rotate with a dual-accept grace window")
async def rotate(key_id: str, principal: Auth, store: Store) -> dict[str, object]:
    principal.require("key:write")
    existing = await store.get_api_key(key_id)
    if existing is None or existing["tenant_id"] != principal.tenant_id:
        raise NotFoundError("key not found", key_id=key_id)

    minted = mint_key(existing["kind"], env="live")
    signing_secret = new_signing_secret() if existing["kind"] == "pub" else ""

    await store.update_api_key(key_id, {"grace_until": time.time() + ROTATION_GRACE_SECONDS})
    await store.create_api_key(
        {
            "tenant_id": principal.tenant_id,
            "key_id": minted.key_id,
            "kind": existing["kind"],
            "name": f"{existing.get('name', 'key')} (rotated)",
            "hash": minted.digest,
            "signing_secret": signing_secret,
            "scopes": existing.get("scopes", []),
            "plan": principal.plan,
            "active": True,
            "rotated_from": key_id,
        }
    )
    return {
        "key_id": minted.key_id,
        "key": minted.plaintext,
        "signing_secret": signing_secret,
        "grace_seconds": ROTATION_GRACE_SECONDS,
    }


@router.delete("/{key_id}", summary="Revoke")
async def revoke(key_id: str, principal: Auth, store: Store, redis: Redis) -> dict[str, object]:
    principal.require("key:write")
    existing = await store.get_api_key(key_id)
    if existing is None or existing["tenant_id"] != principal.tenant_id:
        raise NotFoundError("key not found", key_id=key_id)
    await store.revoke_api_key(key_id, time.time())
    if redis is not None:
        try:
            await redis.set(f"pp:key:revoked:{key_id}", "1", ex=86_400)
        except Exception:
            pass
    return {"ok": True, "key_id": key_id, "revoked": True}
