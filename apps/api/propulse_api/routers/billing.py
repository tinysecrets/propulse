# SPDX-License-Identifier: AGPL-3.0-or-later
"""Headless billing. The 429 is the conversion event."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Request
from propulse_core.entitlements import PLANS, period_reset_at
from propulse_core.errors import ValidationError

from propulse_api.deps import Auth, Billing, Entitlements, Store

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/plans", summary="Public plan catalogue")
async def plans() -> dict[str, object]:
    return {
        "currency": "USD",
        "interval": "month",
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "price_usd": p.price_usd,
                "monthly_pulses": p.monthly_pulses,
                "features": sorted(p.features),
                "overage_allowed": p.overage_allowed,
            }
            for p in PLANS.values()
            if p.id != "enterprise"
        ],
        "checkout_endpoint": "POST /v1/billing/checkout",
    }


@router.post("/checkout", summary="Create a Stripe Checkout session")
async def checkout(
    request: Request,
    principal: Auth,
    billing: Billing,
) -> dict[str, object]:
    principal.require("billing:read")
    body = await request.json()
    plan = body.get("plan", "pro")
    if plan not in PLANS or plan == "free":
        raise ValidationError(
            f"plan {plan!r} is not purchasable", available=[p for p in PLANS if p != "free"]
        )

    result = await billing.create_subscription_checkout(
        tenant_id=principal.tenant_id,
        plan=plan,
        email=body.get("email", ""),
        success_url=body.get("success_url", "https://propulse.wah-lah.com/welcome"),
        cancel_url=body.get("cancel_url", "https://propulse.wah-lah.com/pricing"),
    )
    return {
        "url": result.url,
        "session_id": result.session_id,
        "plan": plan,
        "driver": "stripe" if billing.enabled else "null",
    }


@router.post("/portal", summary="Stripe customer portal URL")
async def portal(
    request: Request, principal: Auth, billing: Billing, store: Store
) -> dict[str, object]:
    principal.require("billing:read")
    sub = await store.get_subscription(principal.tenant_id)
    if not sub or not sub.get("stripe_customer_id"):
        raise ValidationError("no subscription on file — start a checkout first")
    url = await billing.create_portal_session(
        sub["stripe_customer_id"],
        (await request.json()).get("return_url", "https://propulse.wah-lah.com/account"),
    )
    return {"url": url}


@router.get("/entitlements", summary="Current plan, limits and usage")
async def get_entitlements(principal: Auth, entitlements: Entitlements) -> dict[str, object]:
    ent = await entitlements.resolve(principal.tenant_id)
    return {**ent.to_dict(), "reset_at": period_reset_at(), "upgrade_url": entitlements.upgrade_url}


@router.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request, store: Store, billing: Billing, entitlements: Entitlements
) -> dict[str, object]:
    from propulse_api.billing.handlers import dispatch

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = billing.parse_webhook(payload, signature)

    event_id = event.get("id", "")
    if not event_id:
        raise ValidationError("webhook has no event id")

    if not await store.claim_stripe_event(event_id):
        return {"ok": True, "duplicate": True}

    event_type = event.get("type", "unknown")
    handler = dispatch.get(event_type)
    if handler is None:
        log.info("stripe_unhandled", event_type=event_type)
        return {"ok": True, "handled": False}

    await handler(
        event["data"]["object"],
        store=store,
        entitlements=entitlements,
        billing=billing,
        event=event,
    )
    await store.col("stripe_events").update_one(
        {"event_id": event_id},
        {"$set": {"processed": True, "type": event_type, "processed_at": time.time()}},
    )
    return {"ok": True, "handled": True, "type": event_type}
