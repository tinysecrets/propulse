# SPDX-License-Identifier: AGPL-3.0-or-later
"""API key minting and verification.

Asymmetric on purpose:
  pp_pub_*  embedded in app binaries -> SHA-256 (must be fast, verified per request)
  pp_sec_*  server-side secrets      -> Argon2id (slow, verified on cache miss)
Public keys are extractable from an APK. That is fine: security comes from scoping,
request signing, certificate pinning, and per-device rate limits.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmaclib
import os
import secrets
from dataclasses import dataclass
from typing import Literal

from argon2.low_level import Type, hash_secret, verify_secret

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
KEY_ID_LEN = 12
ARGON2_TIME_COST = 3
ARGON2_MEMORY_KIB = 65536
ARGON2_PARALLELISM = 4

KeyKind = Literal["pub", "sec"]
PUBLIC_PREFIX = "pp_pub_"
SECRET_PREFIX = "pp_sec_"

PUBLIC_SCOPES = frozenset({"pulse:signal", "device:register", "pulse:ack", "config:read"})
SECRET_SCOPES = frozenset(
    {
        "pulse:signal",
        "device:register",
        "pulse:ack",
        "config:read",
        "pulse:write",
        "key:write",
        "billing:read",
        "events:read",
        "agent:run",
    }
)


@dataclass(frozen=True, slots=True)
class MintedKey:
    plaintext: str
    key_id: str
    digest: str
    kind: KeyKind
    prefix: str


@dataclass(frozen=True, slots=True)
class ParsedKey:
    kind: KeyKind
    env: str
    key_id: str
    secret: str


def _new_key_id() -> str:
    return "".join(secrets.choice(CROCKFORD) for _ in range(KEY_ID_LEN)).lower()


def mint_key(kind: KeyKind, env: str = "live", *, key_id: str | None = None) -> MintedKey:
    kid = (key_id or _new_key_id()).lower()
    secret = secrets.token_urlsafe(32)
    prefix = PUBLIC_PREFIX if kind == "pub" else SECRET_PREFIX
    plaintext = f"{prefix}{env}_{kid}_{secret}"
    if kind == "pub":
        digest = hashlib.sha256(plaintext.encode()).hexdigest()
    else:
        digest = hash_secret(
            secret=plaintext.encode(),
            salt=os.urandom(16),
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_KIB,
            parallelism=ARGON2_PARALLELISM,
            hash_len=32,
            type=Type.ID,
        ).decode()
    return MintedKey(plaintext=plaintext, key_id=kid, digest=digest, kind=kind, prefix=prefix)


def parse_key(plaintext: str) -> ParsedKey:
    """Parse without touching the DB. O(1), used to find the record."""
    if plaintext.startswith(PUBLIC_PREFIX):
        kind: KeyKind = "pub"
    elif plaintext.startswith(SECRET_PREFIX):
        kind = "sec"
    else:
        raise ValueError("unknown key prefix")
    parts = plaintext.split("_", 4)
    if len(parts) != 5:
        raise ValueError("malformed key")
    _, _, env, key_id, secret = parts
    return ParsedKey(kind=kind, env=env, key_id=key_id, secret=secret)


def verify_key(plaintext: str, digest: str, kind: KeyKind) -> bool:
    if kind == "pub":
        return hmaclib.compare_digest(hashlib.sha256(plaintext.encode()).hexdigest(), digest)
    try:
        return verify_secret(hash=digest.encode(), secret=plaintext.encode(), type=Type.ID)
    except Exception:
        return False


def hash_lookup_token(plaintext: str) -> str:
    """Cheap cache key: never store the plaintext in Redis."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def mask_key(plaintext: str) -> str:
    parsed = parse_key(plaintext)
    return f"{parsed.kind}_...{parsed.key_id}"


def scopes_for(kind: KeyKind, granted: list[str] | None = None) -> frozenset[str]:
    ceiling = PUBLIC_SCOPES if kind == "pub" else SECRET_SCOPES
    if not granted:
        return ceiling
    return frozenset(granted) & ceiling


def new_signing_secret() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
