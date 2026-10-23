# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any

from propulse_core.adapters.billing.null import NullBilling


def make_billing(driver: str, settings: Any) -> Any:
    if driver == "null":
        return NullBilling(upgrade_url=getattr(settings, "upgrade_url", ""))
    if driver == "stripe":
        from propulse_core.adapters.billing.stripe_adapter import StripeBilling

        prices = {
            "STRIPE_PRICE_PRO": settings.stripe_price_pro,
            "STRIPE_PRICE_TEAM": settings.stripe_price_team,
            "STRIPE_PRICE_COMMERCIAL_SINGLE": settings.stripe_price_commercial_single,
            "STRIPE_PRICE_COMMERCIAL_UNLIMITED": settings.stripe_price_commercial_unlimited,
        }
        return StripeBilling(settings.stripe_secret_key, settings.stripe_webhook_secret, prices)
    raise ValueError(f"unknown BILLING_DRIVER={driver!r} (null|stripe)")
