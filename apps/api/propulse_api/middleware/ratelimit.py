# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time

from propulse_core.errors import RateLimited
from propulse_core.ratelimit.tokens import route_cost
from starlette.types import ASGIApp, Receive, Scope, Send

PUBLIC_PATHS = frozenset(
    {"/healthz", "/readyz", "/metrics", "/source", "/v1/plans", "/v1/license/tiers"}
)


class RateLimitMiddleware:
    """Layered buckets: key, tenant, device. Route cost-weighted. Fails open."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in PUBLIC_PATHS or path.startswith(("/docs", "/media")):
            await self.app(scope, receive, send)
            return

        principal = scope.get("state", {}).get("principal")
        bucket = scope["app"].state.rate_limiter
        settings = scope["app"].state.settings

        if principal is None or bucket is None:
            await self.app(scope, receive, send)
            return

        per_min = settings.rate_limit_for(principal.plan)
        rate_per_sec = per_min / 60.0
        burst = max(10, per_min)
        cost = route_cost(path)
        now = int(time.time() * 1000)

        checks = [
            (f"pp:rl:key:{principal.key_id}", rate_per_sec, burst),
            (f"pp:rl:tenant:{principal.tenant_id}", rate_per_sec * 5, burst * 5),
        ]
        headers = {}
        for key, rate, b in checks:
            result = await bucket.consume(key, rate_per_sec=rate, burst=int(b), cost=cost)
            headers["x-ratelimit-limit"] = str(result.limit)
            headers["x-ratelimit-remaining"] = str(result.remaining)
            headers["x-ratelimit-reset"] = str(
                int(time.time()) + max(1, result.retry_after_ms // 1000)
            )
            if not result.allowed:
                err = RateLimited(
                    f"rate limit exceeded for {path}",
                    retry_after_ms=max(result.retry_after_ms, 1000),
                    limit=result.limit,
                    remaining=result.remaining,
                    reset_ms=now,
                )
                await self._reject(send, scope, err, headers)
                return

        scope["state"]["ratelimit_headers"] = headers
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, scope: Scope, err: RateLimited, headers: dict[str, str]) -> None:
        import orjson

        trace_id = scope.get("state", {}).get("trace_id", "")
        hdrs = [
            (b"content-type", b"application/problem+json"),
            (b"retry-after", str(err.retry_after).encode()),
            (b"x-pp-trace", trace_id.encode()),
        ]
        for k, v in headers.items():
            hdrs.append((k.encode(), v.encode()))
        await send({"type": "http.response.start", "status": 429, "headers": hdrs})
        await send({"type": "http.response.body", "body": orjson.dumps(err.to_problem(trace_id))})
