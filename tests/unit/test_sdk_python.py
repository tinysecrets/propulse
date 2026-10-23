# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import hmac

from propulse_sdk.sign import canonical, new_nonce, sign


def test_python_sdk_signing_matches_hmac_contract() -> None:
    secret, ts, nonce, body = "test-secret", "1730000000", "bm9uY2U", '{"ok":true}'
    expected = base64.b64encode(
        hmac.new(
            secret.encode(),
            f"{ts}.{nonce}.{hashlib.sha256(body.encode()).hexdigest()}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    assert canonical(ts, nonce, body) == (
        f"{ts}.{nonce}.{hashlib.sha256(body.encode()).hexdigest()}"
    )
    assert sign(secret, ts, nonce, body) == expected


def test_nonce_is_url_safe_and_128_bits() -> None:
    nonce = new_nonce()
    assert len(nonce) == 22
    assert all(char.isalnum() or char in "-_" for char in nonce)
