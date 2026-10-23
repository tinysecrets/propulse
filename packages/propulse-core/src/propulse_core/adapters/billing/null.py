# SPDX-License-Identifier: AGPL-3.0-or-later
"""Zero-cost default. Everything works with no Stripe account."""

from __future__ import annotations

from typing import Any

from propulse_core.adapters.billing.base import CheckoutResult
from propulse_core.entitlements import PLANS
from propulse_core.licensing import COMMERCIAL_TIERS


class NullBilling:
    enabled = False

    def __init__(self, upgrade_url: str = "") -> None:
        self._upgrade = upgrade_url

    async def create_subscription_checkout(
        self, *, tenant_id: str, plan: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutResult:
        url = f"{self._upgrade}?plan={plan}&tenant={tenant_id}&email={email}"
        return CheckoutResult(url=url, session_id=f"null_{tenant_id}_{plan}", mode="subscription")

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
        url = f"{self._upgrade}?license={tier}&tenant={tenant_id}"
        return CheckoutResult(url=url, session_id=f"null_{tenant_id}_{tier}", mode="payment")

    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        return return_url

    async def report_usage(
        self, *, subscription_item_id: str, quantity: int, timestamp: int
    ) -> None:
        return None

    def parse_webhook(self, payload: bytes, signature: str) -> dict[str, Any]:
        return {}

    @staticmethod
    def plans() -> list[dict[str, Any]]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "price_usd": p.price_usd,
                "monthly_pulses": p.monthly_pulses,
                "features": sorted(p.features),
            }
            for p in PLANS.values()
            if p.id != "enterprise"
        ]

    @staticmethod
    def licenses() -> list[dict[str, Any]]:
        return [
            {"id": t["id"], "name": t["name"], "price_usd": t["price_usd"], "grants": t["grants"]}
            for t in COMMERCIAL_TIERS.values()
        ]
