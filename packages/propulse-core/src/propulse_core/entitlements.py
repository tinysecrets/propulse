# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plan -> limits. Versioned and Redis-cached so a webhook invalidates atomically."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger(__name__)

CACHE_TTL_SECONDS = 60


@dataclass(frozen=True, slots=True)
class Plan:
    id: str
    name: str
    monthly_pulses: int
    rate_limit_per_min: int
    features: frozenset[str] = field(default_factory=frozenset)
    overage_allowed: bool = False
    price_usd: int = 0
    stripe_price_env: str = ""


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        monthly_pulses=1_000,
        rate_limit_per_min=60,
        features=frozenset({"on_device_tts", "basic_triggers"}),
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        monthly_pulses=50_000,
        rate_limit_per_min=600,
        features=frozenset(
            {
                "on_device_tts",
                "cloud_tts",
                "basic_triggers",
                "compound_triggers",
                "voice_coalescing",
                "webhooks",
            }
        ),
        overage_allowed=True,
        price_usd=19,
        stripe_price_env="STRIPE_PRICE_PRO",
    ),
    "team": Plan(
        id="team",
        name="Team",
        monthly_pulses=500_000,
        rate_limit_per_min=3_000,
        features=frozenset(
            {
                "on_device_tts",
                "cloud_tts",
                "basic_triggers",
                "compound_triggers",
                "voice_coalescing",
                "webhooks",
                "seats",
                "audit_export",
                "predictive_send_time",
            }
        ),
        overage_allowed=True,
        price_usd=99,
        stripe_price_env="STRIPE_PRICE_TEAM",
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        monthly_pulses=5_000_000,
        rate_limit_per_min=20_000,
        features=frozenset(
            {
                "on_device_tts",
                "cloud_tts",
                "basic_triggers",
                "compound_triggers",
                "voice_coalescing",
                "webhooks",
                "seats",
                "audit_export",
                "predictive_send_time",
                "self_host_license",
                "sso",
                "priority_support",
            }
        ),
        overage_allowed=True,
        price_usd=0,
    ),
}

DEFAULT_PLAN = "free"


def current_period(now: float | None = None) -> str:
    dt = datetime.fromtimestamp(now or time.time(), tz=UTC)
    return f"{dt.year:04d}-{dt.month:02d}"


def period_reset_at(now: float | None = None) -> str:
    dt = datetime.fromtimestamp(now or time.time(), tz=UTC)
    year, month = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
    return datetime(year, month, 1, tzinfo=UTC).isoformat()


@dataclass(slots=True)
class Entitlements:
    tenant_id: str
    plan: Plan
    features: frozenset[str]
    monthly_limit: int
    used: int
    version: int = 0
    overage_allowed: bool = False
    source: str = "default"

    @property
    def remaining(self) -> int:
        return max(0, self.monthly_limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.monthly_limit

    def has(self, feature: str) -> bool:
        return feature in self.features

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "plan": self.plan.id,
            "features": sorted(self.features),
            "limit": self.monthly_limit,
            "used": self.used,
            "remaining": self.remaining,
            "overage_allowed": self.overage_allowed,
            "source": self.source,
        }


class EntitlementService:
    """Cache keyed by tenant; invalidated by version bump. No thundering herd."""

    def __init__(self, store, redis=None, *, upgrade_url: str = "") -> None:
        self._store = store
        self._redis = redis
        self._upgrade_url = upgrade_url
        self._mem: dict[str, tuple[float, dict[str, Any]]] = {}

    @property
    def upgrade_url(self) -> str:
        return self._upgrade_url

    async def _cached(self, tenant_id: str) -> dict[str, Any] | None:
        if self._redis is not None:
            try:
                raw = await self._redis.get(f"pp:ent:{tenant_id}")
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        hit = self._mem.get(tenant_id)
        if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
        return None

    async def _cache(self, tenant_id: str, data: dict[str, Any]) -> None:
        self._mem[tenant_id] = (time.time(), data)
        if self._redis is not None:
            try:
                await self._redis.set(f"pp:ent:{tenant_id}", json.dumps(data), ex=CACHE_TTL_SECONDS)
            except Exception:
                pass

    async def invalidate(self, tenant_id: str) -> None:
        self._mem.pop(tenant_id, None)
        if self._redis is not None:
            try:
                await self._redis.delete(f"pp:ent:{tenant_id}")
            except Exception:
                pass

    async def resolve(self, tenant_id: str, *, period: str | None = None) -> Entitlements:
        cached = await self._cached(tenant_id)
        if cached is not None:
            plan = PLANS.get(cached["plan"], PLANS[DEFAULT_PLAN])
            return Entitlements(
                tenant_id=tenant_id,
                plan=plan,
                features=frozenset(cached["features"]),
                monthly_limit=cached["limit"],
                used=cached["used"],
                version=cached.get("version", 0),
                overage_allowed=cached.get("overage_allowed", False),
                source="cache",
            )

        period = period or current_period()
        ent_doc = await self._store.get_entitlements(tenant_id) or {}
        plan_id = ent_doc.get("plan", DEFAULT_PLAN)
        plan = PLANS.get(plan_id, PLANS[DEFAULT_PLAN])
        features = frozenset(ent_doc.get("features") or plan.features)
        limit = int(ent_doc.get("monthly_limit", plan.monthly_pulses))
        used = await self._store.get_usage(tenant_id, "pulses", period)

        data = {
            "plan": plan.id,
            "features": sorted(features),
            "limit": limit,
            "used": used,
            "version": int(ent_doc.get("version", 0)),
            "overage_allowed": bool(ent_doc.get("overage_allowed", plan.overage_allowed)),
        }
        await self._cache(tenant_id, data)
        return Entitlements(
            tenant_id=tenant_id,
            plan=plan,
            features=features,
            monthly_limit=limit,
            used=used,
            version=data["version"],
            overage_allowed=data["overage_allowed"],
            source="store",
        )

    async def require_feature(self, tenant_id: str, feature: str) -> Entitlements:
        from propulse_core.errors import ForbiddenError

        ent = await self.resolve(tenant_id)
        if not ent.has(feature):
            raise ForbiddenError(
                f"feature {feature!r} requires an upgraded plan",
                feature=feature,
                plan=ent.plan.id,
                upgrade_url=self._upgrade_url,
            )
        return ent

    async def consume_pulse(self, tenant_id: str, *, qty: int = 1) -> Entitlements:
        from propulse_core.errors import QuotaExceeded

        period = current_period()
        ent = await self.resolve(tenant_id, period=period)
        if ent.exhausted and not ent.overage_allowed:
            raise QuotaExceeded(
                f"monthly pulse quota reached ({ent.used}/{ent.monthly_limit})",
                upgrade_url=self._upgrade_url,
                limit=ent.monthly_limit,
                used=ent.used,
                reset_at=period_reset_at(),
                metric="pulses",
            )
        new_used = await self._store.bump_usage(tenant_id, "pulses", qty, period)
        ent.used = new_used
        await self._cache(
            tenant_id,
            {
                "plan": ent.plan.id,
                "features": sorted(ent.features),
                "limit": ent.monthly_limit,
                "used": new_used,
                "version": ent.version,
                "overage_allowed": ent.overage_allowed,
            },
        )
        return ent
