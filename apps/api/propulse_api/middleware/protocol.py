# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deprecation signalling (RFC 8594) + negotiated protocol echo."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEPRECATED: dict[str, dict[str, str]] = {}


class ProtocolMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                proto = scope.get("state", {}).get("negotiated_protocol")
                if proto:
                    headers.append((b"x-pp-protocol", str(proto).encode()))
                headers.append((b"x-pp-server-time", str(int(__import__("time").time())).encode()))
                for prefix, info in DEPRECATED.items():
                    if path.startswith(prefix):
                        headers.append((b"deprecation", info["deprecation"].encode()))
                        headers.append((b"sunset", info["sunset"].encode()))
                        headers.append((b"link", f'<{info["doc"]}>; rel="deprecation"'.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
