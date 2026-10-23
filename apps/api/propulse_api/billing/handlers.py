# SPDX-License-Identifier: AGPL-3.0-or-later
"""Webhook handlers. Every one is idempotent; the ledger already deduped."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from propulse_core.entitlements import PLANS
from propulse_core.licensing import (
    agreement_text,
    license_id_for,
    mint_commercial_key,
)

log = structlog.get_logger(__name__)

Handler = Callable[..., Awaitable[None]]


async def _apply_plan(
    store,
    entitlements,
    *,
    tenant_id: str,
    plan: str,
    customer_id: str,
    subscription_id: str,
    status: str,
    price_id: str = "",
    period_end: float | None = None,
    event_id: str = "",
) -> None:
    """Upgrade the tenant AND every key it owns. Zero human touchpoints."""
    p = PLANS.get(plan, PLANS["free"])
    await store.upsert_subscription(
        tenant_id,
        {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "status": status,
            "price_id": price_id,
            "plan": p.id,
            "period_end": period_end,
            "updated_at": time.time(),
        },
    )
    await store.upsert_entitlements(
        tenant_id,
        {
            "plan": p.id,
            "features": sorted(p.features),
            "monthly_limit": p.monthly_pulses,
            "overage_allowed": p.overage_allowed,
        },
    )
    await entitlements.invalidate(tenant_id)

    for key in await store.list_api_keys(tenant_id):
        await store.update_api_key(key["key_id"], {"plan": p.id})

    await store.audit(
        {
            "tenant_id": tenant_id,
            "action": "plan_changed",
            "plan": p.id,
            "status": status,
            "stripe_event": event_id,
        }
    )
    log.info("plan_applied", tenant_id=tenant_id, plan=p.id, status=status)


async def on_checkout_completed(
    obj: dict[str, Any], *, store, entitlements, billing, event
) -> None:
    meta = obj.get("metadata") or {}
    tenant_id = meta.get("tenant_id") or obj.get("client_reference_id", "")

    if meta.get("kind") == "license":
        await _issue_license(
            obj,
            store=store,
            tenant_id=tenant_id,
            tier=meta.get("tier", "single"),
            licensee=meta.get("licensee", ""),
            event=event,
        )
        return

    plan = meta.get("plan", "pro")
    await _apply_plan(
        store,
        entitlements,
        tenant_id=tenant_id,
        plan=plan,
        customer_id=obj.get("customer", ""),
        subscription_id=obj.get("subscription", ""),
        status="active",
        event_id=event.get("id", ""),
    )


async def _issue_license(
    obj: dict[str, Any], *, store, tenant_id: str, tier: str, licensee: str, event
) -> None:
    from propulse_core.licensing import COMMERCIAL_TIERS as TIERS

    if tier not in TIERS:
        tier = "single"
    session_id = obj.get("id", "")
    license_id = license_id_for(session_id)
    email = obj.get("customer_details", {}).get("email", "")
    now = time.time()
    import os

    secret = os.environ.get("LICENSE_SIGNING_SECRET", "")
    expires_at = int(now + 365 * 86_400 * 100)
    key = (
        mint_commercial_key(tier, expires_at, secret)
        if secret
        else f"PP-C-{tier.upper()}-{expires_at}-00000000"
    )

    await store.create_license(
        {
            "license_id": license_id,
            "tenant_id": tenant_id,
            "tier": tier,
            "licensee": licensee or email or "Unnamed Licensee",
            "email": email,
            "license_key": key,
            "stripe_session_id": session_id,
            "amount_usd": TIERS[tier]["price_usd"],
            "status": "active",
            "issued_at": now,
            "agreement": agreement_text(
                tier=tier,
                licensee=licensee or email or "Unnamed Licensee",
                email=email,
                license_key=key,
                issued_at=now,
            ),
            "github_access": "pending",
        }
    )

    await store.upsert_entitlements(
        tenant_id,
        {
            "plan": "enterprise",
            "features": sorted(PLANS["enterprise"].features | {"commercial_license"}),
            "monthly_limit": PLANS["enterprise"].monthly_pulses,
            "overage_allowed": True,
            "commercial_tier": tier,
        },
    )
    await store.audit(
        {
            "tenant_id": tenant_id,
            "action": "commercial_license_issued",
            "tier": tier,
            "amount_usd": TIERS[tier]["price_usd"],
            "license_id": license_id,
            "stripe_event": event.get("id", ""),
        }
    )
    log.info(
        "commercial_license_issued",
        tenant_id=tenant_id,
        tier=tier,
        license_id=license_id,
        mrr_equivalent_usd=TIERS[tier]["price_usd"],
    )


async def on_subscription_updated(
    obj: dict[str, Any], *, store, entitlements, billing, event
) -> None:
    customer_id = obj.get("customer", "")
    sub = await store.find_subscription_by_customer(customer_id)
    if sub is None:
        return
    meta = obj.get("metadata") or {}
    status = obj.get("status", "")
    plan = meta.get("plan", sub.get("plan", "free"))
    if status in ("past_due", "unpaid"):
        plan = "pro" if sub.get("plan") in ("pro", "team") else "free"
    elif status in ("canceled", "incomplete_expired"):
        plan = "free"

    period_end = float(obj.get("current_period_end", 0) or 0)
    await _apply_plan(
        store,
        entitlements,
        tenant_id=sub["tenant_id"],
        plan=plan,
        customer_id=customer_id,
        subscription_id=obj.get("id", ""),
        status=status,
        period_end=period_end,
        event_id=event.get("id", ""),
    )


async def on_subscription_deleted(
    obj: dict[str, Any], *, store, entitlements, billing, event
) -> None:
    customer_id = obj.get("customer", "")
    sub = await store.find_subscription_by_customer(customer_id)
    if sub is None:
        return
    await _apply_plan(
        store,
        entitlements,
        tenant_id=sub["tenant_id"],
        plan="free",
        customer_id=customer_id,
        subscription_id=obj.get("id", ""),
        status="canceled",
        event_id=event.get("id", ""),
    )


async def on_payment_failed(obj: dict[str, Any], *, store, entitlements, billing, event) -> None:
    customer_id = obj.get("customer", "")
    sub = await store.find_subscription_by_customer(customer_id)
    if sub is None:
        return
    await store.upsert_subscription(
        sub["tenant_id"],
        {
            **{k: v for k, v in sub.items() if k != "_id"},
            "status": "past_due",
            "grace_until": time.time() + 7 * 86_400,
        },
    )
    await store.audit({"tenant_id": sub["tenant_id"], "action": "payment_failed", "grace_days": 7})


async def on_invoice_paid(obj: dict[str, Any], *, store, entitlements, billing, event) -> None:
    customer_id = obj.get("customer", "")
    sub = await store.find_subscription_by_customer(customer_id)
    if sub is None:
        return
    await store.upsert_subscription(
        sub["tenant_id"],
        {
            **{k: v for k, v in sub.items() if k != "_id"},
            "status": "active",
            "last_invoice_at": time.time(),
        },
    )


dispatch: dict[str, Handler] = {
    "checkout.session.completed": on_checkout_completed,
    "customer.subscription.updated": on_subscription_updated,
    "customer.subscription.deleted": on_subscription_deleted,
    "invoice.payment_failed": on_payment_failed,
    "invoice.paid": on_invoice_paid,
}
