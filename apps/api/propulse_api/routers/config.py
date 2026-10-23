# SPDX-License-Identifier: AGPL-3.0-or-later
"""Public, CDN-cacheable config. Kills SDK cold-start latency."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from propulse_core.protocol import PROTOCOL_MIN_SUPPORTED, PROTOCOL_VERSION

router = APIRouter(prefix="/v1", tags=["config"])


@router.get("/config", summary="Public SDK configuration")
async def config(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    response.headers["cache-control"] = "public, max-age=300, stale-while-revalidate=600"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_min": PROTOCOL_MIN_SUPPORTED,
        "poll": {"default_s": 300, "min_s": 60, "max_s": 900, "jitter": True},
        "features": {
            "compound_triggers": settings.flag_compound_triggers,
            "predictive_send_time": settings.flag_predictive_send_time,
            "voice_coalescing": True,
            "server_tts": settings.tts_driver not in ("device", "none"),
        },
        "kill_switch": settings.global_kill,
        "upgrade_url": settings.upgrade_url,
        "signing": {"required": True, "window_s": 300, "algorithm": "HMAC-SHA256"},
        "tts": {"default": settings.tts_driver, "max_chars": 220},
    }


@router.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt() -> Response:
    body = (
        "Contact: security@wah-lah.com\n"
        "Expires: 2027-10-23T00:00:00.000Z\n"
        "Preferred-Languages: en\n"
        "Canonical: https://propulse.wah-lah.com/.well-known/security.txt\n"
        "Policy: https://github.com/tinysecrets/propulse/blob/main/SECURITY.md\n"
    )
    return Response(content=body, media_type="text/plain")
