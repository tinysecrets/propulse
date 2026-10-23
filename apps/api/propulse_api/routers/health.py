# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from propulse_core import __version__

router = APIRouter(tags=["ops"])
_STARTED = time.time()


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, object]:
    return {"status": "ok", "version": __version__, "uptime_s": int(time.time() - _STARTED)}


@router.get("/readyz", include_in_schema=False)
async def readyz(request: Request, response: Response) -> dict[str, object]:
    store = request.app.state.store
    redis = request.app.state.redis
    checks: dict[str, bool] = {"mongo": await store.ping()}
    if redis is not None:
        try:
            await redis.ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
    ready = checks["mongo"] and checks.get("redis", True)
    response.status_code = 200 if ready else 503
    return {"ready": ready, "checks": checks, "version": __version__}


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    registry = getattr(request.app.state, "metrics_registry", None)
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
