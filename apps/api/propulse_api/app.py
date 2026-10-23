# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from propulse_api.middleware.auth import AuthMiddleware
from propulse_api.middleware.context import RequestContextMiddleware
from propulse_api.middleware.idempotency import IdempotencyMiddleware
from propulse_api.middleware.protocol import ProtocolMiddleware
from propulse_api.middleware.ratelimit import RateLimitMiddleware
from propulse_api.middleware.security_headers import SecurityHeadersMiddleware
from propulse_api.routers import (
    billing,
    config,
    devices,
    health,
    keys,
    pulses,
    source,
)
from propulse_api.routers import (
    license as license_router,
)
from propulse_api.settings import Settings
from propulse_core import __version__
from propulse_core.adapters.billing.factory import make_billing
from propulse_core.bus.factory import make_bus
from propulse_core.entitlements import EntitlementService
from propulse_core.errors import ProPulseError
from propulse_core.logging import configure_logging
from propulse_core.ratelimit.tokens import TokenBucket
from propulse_core.storage.mongo import MongoStore
from redis.asyncio import Redis

log = structlog.get_logger(__name__)

DESCRIPTION = """
**Make any app proactive.** ProPulse is a background event-driven agent orchestrator.

* `pp_pub_*` keys are embedded in app binaries and require HMAC request signing.
* `pp_secret_*` keys are server-side and may call privileged routes.
* Hitting a quota returns `429` with an `upgrade_url` — that is the whole billing funnel.

Server is **AGPL-3.0-or-later**. `GET /source` satisfies section 13.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.store = MongoStore(
            settings.mongo_uri, settings.mongo_db, max_pool_size=settings.mongo_max_pool_size
        )
        await app.state.store.connect()
        await app.state.store.ensure_indexes()

        try:
            app.state.redis = Redis.from_url(settings.redis_url, decode_responses=False)
            await app.state.redis.ping()
        except Exception as exc:
            log.warning("redis_unavailable", error=str(exc))
            app.state.redis = None

        app.state.bus = make_bus(settings.bus_driver, settings.redis_url)
        app.state.billing = make_billing(settings.billing_driver, settings)
        app.state.rate_limiter = TokenBucket(
            app.state.redis, fail_open=settings.rate_limit_fail_open
        )
        app.state.entitlements = EntitlementService(
            app.state.store, app.state.redis, upgrade_url=settings.upgrade_url
        )
        log.info(
            "started",
            version=__version__,
            env=settings.env,
            bus=settings.bus_driver,
            billing=settings.billing_driver,
            llm=settings.llm_driver,
            tts=settings.tts_driver,
        )
        yield
        await app.state.bus.close()
        if app.state.redis is not None:
            await app.state.redis.aclose()
        await app.state.store.close()

    app = FastAPI(
        title="Wah-Lah ProPulse AI",
        description=DESCRIPTION,
        version=__version__,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "Wah-Lah", "email": "eng@wah-lah.com"},
        license_info={
            "name": "AGPL-3.0-or-later",
            "url": "https://www.gnu.org/licenses/agpl-3.0.html",
        },
    )

    # Middleware: outermost first.
    app.add_middleware(ProtocolMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestContextMiddleware)

    for r in (health, source, config, pulses, devices, keys, billing, license_router):
        app.include_router(r.router)

    @app.exception_handler(ProPulseError)
    async def _propulse_error(request: Request, exc: ProPulseError):
        trace_id = getattr(request.state, "trace_id", "")
        headers: dict[str, str] = {}
        if getattr(exc, "retry_after", None):
            headers["retry-after"] = str(exc.retry_after)
        if isinstance(exc, type(exc)) and hasattr(exc, "upgrade_url"):
            headers["x-pp-upgrade-url"] = getattr(exc, "upgrade_url", "")
        return ORJSONResponse(
            exc.to_problem(trace_id),
            status_code=exc.http_status,
            headers=headers,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", "")
        return ORJSONResponse(
            {
                "type": "https://propulse.wah-lah.com/errors/validation_error",
                "title": "Validation Error",
                "status": 422,
                "detail": "request body failed validation",
                "trace_id": trace_id,
                "errors": exc.errors(),
            },
            status_code=422,
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", "")
        log.exception("unhandled", trace_id=trace_id)
        return ORJSONResponse(
            {
                "type": "https://propulse.wah-lah.com/errors/internal_error",
                "title": "Internal Error",
                "status": 500,
                "detail": "an unexpected error occurred",
                "trace_id": trace_id,
            },
            status_code=500,
            media_type="application/problem+json",
        )

    return app
