# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from typing import Any

import pytest
from propulse_api.middleware.auth import AuthMiddleware


async def _downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _request(middleware: AuthMiddleware, path: str, headers: list[tuple[bytes, bytes]]):
    scope = {"type": "http", "path": path, "headers": headers, "state": {"trace_id": "trace-test"}}
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_public_billing_route_bypasses_api_key_auth() -> None:
    messages = await _request(AuthMiddleware(_downstream), "/v1/billing/plans", [])
    assert messages[0]["status"] == 204


@pytest.mark.asyncio
async def test_missing_api_key_returns_problem_document() -> None:
    messages = await _request(AuthMiddleware(_downstream), "/v1/pulses", [])
    assert messages[0]["status"] == 401
    body = json.loads(messages[1]["body"])
    assert body["title"] == "Missing Api Key"
    assert body["trace_id"] == "trace-test"


@pytest.mark.asyncio
async def test_malformed_api_key_is_rejected_before_store_access() -> None:
    messages = await _request(
        AuthMiddleware(_downstream), "/v1/pulses", [(b"x-pp-key", b"not-a-key")]
    )
    assert messages[0]["status"] == 401
    assert json.loads(messages[1]["body"])["title"] == "Malformed Api Key"


@pytest.mark.asyncio
async def test_non_http_scope_is_passed_through() -> None:
    called = False

    async def downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
        nonlocal called
        called = True

    async def receive() -> dict[str, Any]:
        return {}

    async def send(message: dict[str, Any]) -> None:
        return None

    await AuthMiddleware(downstream)({"type": "websocket"}, receive, send)
    assert called
