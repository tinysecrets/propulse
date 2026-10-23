# SPDX-License-Identifier: AGPL-3.0-or-later
"""API key auth + HMAC replay protection + protocol negotiation."""

from __future__ import annotations

import time

import structlog
from propulse_core.security.hmac import (
    HEADER_KEY,
    HEADER_NONCE,
    HEADER_PROTOCOL,
    HEADER_SERVER_TIME,
    HEADER_SIG,
    HEADER_TS,
    timestamp_ok,
)
from propulse_core.security.hmac import (
    verify as hmac_verify,
)
from propulse_core.security.keys import parse_key, scopes_for, verify_key
from starlette.types import ASGIApp, Receive, Scope, Send

log = structlog.get_logger(__name__)

PUBLIC_PATHS = frozenset(
    {
        "/healthz",
        "/readyz",
        "/metrics",
        "/source",
        "/v1/billing/webhook",
        "/v1/plans",
        "/v1/license/tiers",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/.well-known/security.txt",
    }
)

NONCE_TTL_SECONDS = 300


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in PUBLIC_PATHS or path.startswith(("/media", "/docs")):
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers") or []}
        raw_key = headers.get(HEADER_KEY, "")
        if not raw_key:
            await self._fail(
                send, scope, 401, "missing_api_key", f"provide the {HEADER_KEY} header"
            )
            return

        try:
            parsed = parse_key(raw_key)
        except ValueError as exc:
            await self._fail(send, scope, 401, "malformed_api_key", str(exc))
            return

        store = scope["app"].state.store
        record = await store.get_api_key(parsed.key_id)
        if record is None or not record.get("active", True):
            await self._fail(send, scope, 401, "invalid_api_key", "key not found or revoked")
            return
        if record.get("revoked_at"):
            await self._fail(send, scope, 401, "revoked_api_key", "key has been revoked")
            return

        if not verify_key(raw_key, record["hash"], parsed.kind):
            await self._fail(send, scope, 401, "invalid_api_key", "signature mismatch")
            return

        # HMAC is mandatory for public keys (they travel inside APK/IPA files).
        if parsed.kind == "pub":
            ts_raw, nonce, sig = (
                headers.get(HEADER_TS),
                headers.get(HEADER_NONCE),
                headers.get(HEADER_SIG),
            )
            if not (ts_raw and nonce and sig):
                await self._fail(
                    send,
                    scope,
                    401,
                    "unsigned_request",
                    f"{HEADER_TS}, {HEADER_NONCE}, {HEADER_SIG} are required",
                )
                return
            try:
                ts = int(ts_raw)
            except ValueError:
                await self._fail(send, scope, 401, "bad_timestamp", "x-pp-ts must be an int")
                return
            if not timestamp_ok(ts):
                await self._fail(
                    send,
                    scope,
                    401,
                    "stale_timestamp",
                    "clock skew beyond 300s",
                    extra={HEADER_SERVER_TIME: str(int(time.time()))},
                )
                return
            secret = record.get("signing_secret") or ""
            body = scope["state"].get("raw_body", b"")
            if not hmac_verify(secret, ts, nonce, body, sig):
                await self._fail(send, scope, 401, "bad_signature", "HMAC mismatch")
                return
            redis = scope["app"].state.redis
            if redis is not None:
                try:
                    fresh = await redis.set(
                        f"pp:nonce:{record['key_id']}:{nonce}", "1", ex=NONCE_TTL_SECONDS, nx=True
                    )
                    if not fresh:
                        await self._fail(send, scope, 401, "replayed_nonce", "nonce already used")
                        return
                except Exception:
                    pass  # fail-open: Redis loss must not be an outage

        # Protocol negotiation: client may be older or newer than us.
        from propulse_core.protocol import PROTOCOL_MIN_SUPPORTED, PROTOCOL_VERSION

        client_proto = int(headers.get(HEADER_PROTOCOL, PROTOCOL_VERSION))
        negotiated = min(max(client_proto, PROTOCOL_MIN_SUPPORTED), PROTOCOL_VERSION)

        from propulse_api.deps import Principal

        scopes = scopes_for(parsed.kind, record.get("scopes"))
        scope["state"]["principal"] = Principal(
            tenant_id=record["tenant_id"],
            key_id=record["key_id"],
            kind=parsed.kind,
            scopes=scopes,
            plan=record.get("plan", "free"),
            auth_method="hmac" if parsed.kind == "pub" else "key",
        )
        scope["state"]["negotiated_protocol"] = negotiated

        await self.app(scope, receive, send)

    @staticmethod
    async def _fail(
        send: Send,
        scope: Scope,
        status: int,
        code: str,
        detail: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        import orjson

        trace_id = scope.get("state", {}).get("trace_id", "")
        body = {
            "type": f"https://propulse.wah-lah.com/errors/{code}",
            "title": code.replace("_", " ").title(),
            "status": status,
            "detail": detail,
        }
        if trace_id:
            body["trace_id"] = trace_id
        headers = [
            (b"content-type", b"application/problem+json"),
            (b"x-pp-trace", trace_id.encode()),
        ]
        for k, v in (extra or {}).items():
            headers.append((k.encode(), v.encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": orjson.dumps(body)})
