# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def digest(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def canonical(ts: str | int, nonce: str, body: str) -> str:
    return f"{ts}.{nonce}.{digest(body)}"


def sign(secret: str, ts: str | int, nonce: str, body: str) -> str:
    mac = hmac.new(secret.encode(), canonical(ts, nonce, body).encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def new_nonce() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")
