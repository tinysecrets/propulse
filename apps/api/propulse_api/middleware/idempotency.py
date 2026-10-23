# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import hashlib
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

IDEMPOTENT_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
TTL_SECONDS = 86_400


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in IDEMPOTENT_METHODS:
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers") or []}
        key = headers.get("idempotency-key")
        redis = scope["app"].state.redis
        principal = scope.get("state", {}).get("principal")
        if not key or redis is None or principal is None:
            await self.app(scope, receive, send)
            return

        body = scope["state"].get("raw_body", b"")
        fingerprint = hashlib.sha256(
            f"{principal.tenant_id}:{scope['method']}:{scope['path']}:{key}:".encode() + body
        ).hexdigest()
        cache_key = f"pp:idem:{fingerprint}"

        try:
            cached = await redis.get(cache_key)
        except Exception:
            cached = None

        if cached:
            import orjson

            record = orjson.loads(cached)
            await send(
                {
                    "type": "http.response.start",
                    "status": record["status"],
                    "headers": [(k.encode(), v.encode()) for k, v in record["headers"].items()]
                    + [(b"x-pp-idempotent-replay", b"true")],
                }
            )
            await send({"type": "http.response.body", "body": record["body"]})
            return

        captured: dict[str, Any] = {"status": 500, "headers": {}, "body": b""}

        async def capture_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = {
                    k.decode().lower(): v.decode() for k, v in message.get("headers", [])
                }
            elif message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")
                if message.get("more_body"):
                    return
            await send(message)

        await self.app(scope, receive, capture_send)

        if 200 <= captured["status"] < 300:
            import orjson

            try:
                await redis.set(
                    cache_key,
                    orjson.dumps(
                        {
                            "status": captured["status"],
                            "headers": {
                                k: v
                                for k, v in captured["headers"].items()
                                if k not in ("content-length", "date", "server")
                            },
                            "body": captured["body"],
                        }
                    ),
                    ex=TTL_SECONDS,
                )
            except Exception:
                pass
