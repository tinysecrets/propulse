# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from propulse_core.errors import NotFoundError, ValidationError
from propulse_core.licensing import (
    COMMERCIAL_TIERS,
    is_signed_commercial,
)

from propulse_api.deps import Auth, Billing, Store

router = APIRouter(prefix="/v1/license", tags=["license"])


@router.post("/checkout", summary="Buy a commercial buy-out ($15k / $25k)")
async def license_checkout(
    request: Request,
    principal: Auth,
    billing: Billing,
) -> dict[str, object]:
    body = await request.json()
    tier = body.get("tier", "single")
    if tier not in COMMERCIAL_TIERS:
        raise ValidationError(f"unknown tier {tier!r}", available=list(COMMERCIAL_TIERS))

    result = await billing.create_license_checkout(
        tenant_id=principal.tenant_id,
        tier=tier,
        email=body.get("email", ""),
        licensee=body.get("licensee", body.get("company", "")),
        success_url=body.get("success_url", "https://propulse.wah-lah.com/license/thanks"),
        cancel_url=body.get("cancel_url", "https://propulse.wah-lah.com/license"),
    )
    t = COMMERCIAL_TIERS[tier]
    return {
        "url": result.url,
        "session_id": result.session_id,
        "tier": tier,
        "price_usd": t["price_usd"],
        "renewal_usd": t["renewal_usd"],
        "grants": t["grants"],
    }


@router.post("/quote", summary="Instant quote — no sales call")
async def quote(request: Request) -> dict[str, object]:
    body = await request.json()
    tier = body.get("tier", "single")
    if tier not in COMMERCIAL_TIERS:
        raise ValidationError(f"unknown tier {tier!r}", available=list(COMMERCIAL_TIERS))
    t = COMMERCIAL_TIERS[tier]
    return {
        "tier": tier,
        "name": t["name"],
        "price_usd": t["price_usd"],
        "renewal_usd": t["renewal_usd"],
        "grants": t["grants"],
        "delivery": "License key instantly, private repo access within 1 business day.",
        "payment": "Stripe Checkout, one-time. Card, SEPA, ACH.",
        "contact": "licensing@wah-lah.com",
    }


@router.get("/{license_id}", summary="Retrieve a license and its agreement")
async def get_license(license_id: str, principal: Auth, store: Store) -> dict[str, object]:
    lic = await store.get_license(license_id)
    if lic is None or lic["tenant_id"] != principal.tenant_id:
        raise NotFoundError("license not found", license_id=license_id)
    out = dict(lic)
    out.pop("_id", None)
    return out


@router.post("/verify", summary="Offline-verifiable license check")
async def verify(body: dict[str, Any]) -> dict[str, object]:
    key = body.get("license_key", "")
    import os

    secret = os.environ.get("LICENSE_SIGNING_SECRET", "")
    valid = is_signed_commercial(key, secret=secret) if secret else is_signed_commercial(key)
    parts = key.split("-")
    return {
        "valid": valid,
        "tier": parts[2].lower() if valid and len(parts) > 2 else None,
        "expires_at": int(parts[3]) if valid and len(parts) > 3 and parts[3].isdigit() else None,
        "license": "Commercial Buy-Out — AGPL section 13 obligations waived",
    }


@router.get("/{license_id}/agreement", summary="Plain-text dual-license agreement")
async def agreement(license_id: str, principal: Auth, store: Store) -> dict[str, object]:
    lic = await store.get_license(license_id)
    if lic is None or lic["tenant_id"] != principal.tenant_id:
        raise NotFoundError("license not found", license_id=license_id)
    return {
        "license_id": license_id,
        "agreement": lic.get("agreement", ""),
        "sha256_url": f"/v1/license/{license_id}/agreement.txt",
    }
