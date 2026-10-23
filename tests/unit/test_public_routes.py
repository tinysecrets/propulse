# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_api.middleware.auth import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from propulse_api.middleware.ratelimit import PUBLIC_PATHS as RATE_LIMIT_PUBLIC_PATHS


def test_billing_plan_catalog_is_public_without_an_api_key() -> None:
    assert "/v1/billing/plans" in AUTH_PUBLIC_PATHS
    assert "/v1/billing/plans" in RATE_LIMIT_PUBLIC_PATHS


def test_entitlement_catalog_is_public_without_an_api_key() -> None:
    assert "/v1/entitlements/tiers" in AUTH_PUBLIC_PATHS
    assert "/v1/entitlements/tiers" in RATE_LIMIT_PUBLIC_PATHS
