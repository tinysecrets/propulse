# SPDX-License-Identifier: AGPL-3.0-or-later
"""Replay-proof request signing for mobile clients."""

from __future__ import annotations

import base64
import hashlib
import hmac as hmaclib
import secrets
import time

SIGNATURE_WINDOW_SECONDS = 300
NONCE_BYTES = 16

HEADER_KEY = "x-pp-key"
HEADER_TS = "x-pp-ts"
HEADER_NONCE = "x-pp-nonce"
HEADER_SIG = "x-pp-sig"
HEADER_PROTOCOL = "x-pp-protocol"
HEADER_SERVER_TIME = "x-pp-server-time"


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical(ts: int | str, nonce: str, body: bytes) -> bytes:
    return f"{ts}.{nonce}.{body_digest(body)}".encode()


def sign(signing_secret: str, ts: int, nonce: str, body: bytes) -> str:
    mac = hmaclib.new(signing_secret.encode(), canonical(ts, nonce, body), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def verify(signing_secret: str, ts: int, nonce: str, body: bytes, signature: str) -> bool:
    expected = sign(signing_secret, ts, nonce, body)
    return hmaclib.compare_digest(expected, signature)


def timestamp_ok(
    ts: int, *, now: int | None = None, window: int = SIGNATURE_WINDOW_SECONDS
) -> bool:
    now = now if now is not None else int(time.time())
    return abs(now - ts) <= window


def new_nonce() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(NONCE_BYTES)).decode().rstrip("=")
