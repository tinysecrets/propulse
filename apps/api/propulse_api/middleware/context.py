# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pure-ASGI: buffers the body so HMAC can read it, then replays it downstream."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = structlog.get_logger(__name__)

MAX_BODY_BYTES = 1024 * 1024
SMALL_BODY_PATHS = ("/v1/pulses:signal", "/v1/pulses/ack")
SMALL_BODY_BYTES = 64 * 1024


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = (
            dict(scope.get("headers") or {}).get(b"x-pp-trace", b"").decode()
            or uuid.uuid4().hex[:16]
        )
        scope.setdefault("state", {})
        scope["state"]["trace_id"] = trace_id
        scope["state"]["started_at"] = time.perf_counter()

        path = scope.get("path", "")
        limit = (
            SMALL_BODY_BYTES
            if any(path.startswith(p) for p in SMALL_BODY_PATHS)
            else MAX_BODY_BYTES
        )

        body = bytearray()
        more = True
        while more:
            message: Message = await receive()
            if message["type"] != "http.request":
                if message["type"] == "http.disconnect":
                    return
                continue
            body.extend(message.get("body", b""))
            if len(body) > limit:
                from propulse_core.errors import ValidationError

                err = ValidationError(f"body exceeds {limit} bytes", limit=limit)
                await self._reject(send, err, trace_id)
                return
            more = message.get("more_body", False)

        scope["state"]["raw_body"] = bytes(body)

        async def replay() -> Message:
            return {"type": "http.request", "body": scope["state"]["raw_body"], "more_body": False}

        structlog.contextvars.bind_contextvars(trace_id=trace_id, path=path)
        try:
            await self.app(scope, replay, send)
        finally:
            structlog.contextvars.unbind_contextvars("trace_id", "path")

    @staticmethod
    async def _reject(send: Send, err: Any, trace_id: str) -> None:
        import orjson

        payload = orjson.dumps(err.to_problem(trace_id))
        await send(
            {
                "type": "http.response.start",
                "status": err.http_status,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"x-pp-trace", trace_id.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
