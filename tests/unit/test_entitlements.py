# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from propulse_core.entitlements import (
    PLANS,
    EntitlementService,
    current_period,
    period_reset_at,
)
from propulse_core.errors import ForbiddenError, QuotaExceeded


class FakeStore:
    def __init__(self, plan="free", limit=1000):
        self.ent = {
            "plan": plan,
            "monthly_limit": limit,
            "features": sorted(PLANS[plan].features),
            "version": 1,
        }
        self.usage = 0

    async def get_entitlements(self, _):
        return self.ent

    async def get_usage(self, *_):
        return self.usage

    async def bump_usage(self, _, metric, qty, period):
        self.usage += qty
        return self.usage


def test_free_plan_has_no_overage():
    assert not PLANS["free"].overage_allowed


def test_paid_plans_allow_overage():
    for plan_id in ("pro", "team"):
        assert PLANS[plan_id].overage_allowed


def test_period_format():
    assert current_period(0).count("-") == 1
    assert "T" in period_reset_at(0)


async def test_free_tenant_raises_quota_with_upgrade_url():
    store = FakeStore(plan="free", limit=2)
    svc = EntitlementService(store, None, upgrade_url="https://x/upgrade")
    await svc.consume_pulse("t")
    await svc.consume_pulse("t")
    with pytest.raises(QuotaExceeded) as exc:
        await svc.consume_pulse("t")
    assert exc.value.upgrade_url == "https://x/upgrade"
    assert exc.value.http_status == 429
    assert exc.value.details["reset_at"]


async def test_pro_plan_allows_overage():
    store = FakeStore(plan="pro", limit=1)
    svc = EntitlementService(store, None)
    await svc.consume_pulse("t")
    await svc.consume_pulse("t")
    assert (await svc.resolve("t")).used == 2


async def test_feature_gate_raises_forbidden():
    svc = EntitlementService(FakeStore(plan="free"), None, upgrade_url="https://x")
    await svc.resolve("t")
    with pytest.raises(ForbiddenError):
        await svc.require_feature("t", "compound_triggers")


async def test_feature_gate_passes_on_pro():
    svc = EntitlementService(FakeStore(plan="pro"), None)
    await svc.resolve("t")
    ent = await svc.require_feature("t", "compound_triggers")
    assert ent.plan.id == "pro"


async def test_cache_is_invalidatable():
    svc = EntitlementService(FakeStore(), None)
    assert (await svc.resolve("t")).source == "store"
    assert (await svc.resolve("t")).source == "cache"
    await svc.invalidate("t")
    assert (await svc.resolve("t")).source == "store"
