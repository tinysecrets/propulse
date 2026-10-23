# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any

import structlog
from propulse_core.adapters.billing.base import CheckoutResult
from propulse_core.entitlements import PLANS
from propulse_core.errors import ValidationError
from propulse_core.licensing import COMMERCIAL_TIERS

log = structlog.get_logger(__name__)


class StripeBilling:
    enabled = True

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        prices: dict[str, str],
        *,
        tax_enabled: bool = True,
    ) -> None:
        import stripe

        self._stripe = stripe
        stripe.api_key = secret_key
        self._webhook_secret = webhook_secret
        self._prices = prices
        self._tax = tax_enabled

    def _price_for_plan(self, plan: str) -> str:
        if plan not in PLANS or plan == "free":
            raise ValidationError(f"plan {plan!r} is not purchasable")
        env = PLANS[plan].stripe_price_env
        price = self._prices.get(env)
        if not price:
            raise ValidationError(f"price not configured for plan {plan!r}", env=env)
        return price

    def _price_for_tier(self, tier: str) -> str:
        if tier not in COMMERCIAL_TIERS:
            raise ValidationError(f"unknown license tier {tier!r}")
        env = COMMERCIAL_TIERS[tier]["stripe_price_env"]
        price = self._prices.get(env)
        if not price:
            raise ValidationError(f"price not configured for tier {tier!r}", env=env)
        return price

    async def create_subscription_checkout(
        self, *, tenant_id: str, plan: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutResult:
        session = await self._stripe.checkout.Session.create_async(
            mode="subscription",
            line_items=[{"price": self._price_for_plan(plan), "quantity": 1}],
            customer_email=email or None,
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
            automatic_tax={"enabled": self._tax},
            allow_promotion_codes=True,
            subscription_data={"metadata": {"tenant_id": tenant_id, "plan": plan}},
            metadata={"tenant_id": tenant_id, "plan": plan, "kind": "subscription"},
            client_reference_id=tenant_id,
        )
        return CheckoutResult(url=session.url, session_id=session.id, mode="subscription")

    async def create_license_checkout(
        self,
        *,
        tenant_id: str,
        tier: str,
        email: str,
        licensee: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        t = COMMERCIAL_TIERS[tier]
        session = await self._stripe.checkout.Session.create_async(
            mode="payment",
            line_items=[{"price": self._price_for_tier(tier), "quantity": 1}],
            customer_email=email or None,
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
            automatic_tax={"enabled": self._tax},
            payment_intent_data={
                "metadata": {"tenant_id": tenant_id, "tier": tier, "kind": "license"}
            },
            metadata={
                "tenant_id": tenant_id,
                "tier": tier,
                "licensee": licensee,
                "kind": "license",
            },
            client_reference_id=tenant_id,
            invoice_creation={"enabled": True},
        )
        log.info(
            "license_checkout_created", tenant_id=tenant_id, tier=tier, amount_usd=t["price_usd"]
        )
        return CheckoutResult(url=session.url, session_id=session.id, mode="payment")

    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        session = await self._stripe.billing_portal.Session.create_async(
            customer=customer_id, return_url=return_url
        )
        return session.url

    async def report_usage(
        self, *, subscription_item_id: str, quantity: int, timestamp: int
    ) -> None:
        await self._stripe.SubscriptionItem.create_usage_record_async(
            subscription_item_id,
            quantity=quantity,
            timestamp=timestamp,
            action="set",
        )

    def parse_webhook(self, payload: bytes, signature: str) -> dict[str, Any]:
        try:
            event = self._stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
        except Exception as exc:
            raise ValidationError(f"invalid stripe signature: {exc}") from exc
        return dict(event)

    async def retrieve_session(self, session_id: str) -> dict[str, Any]:
        return dict(await self._stripe.checkout.Session.retrieve_async(session_id))
