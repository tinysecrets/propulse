# SPDX-License-Identifier: AGPL-3.0-or-later
import time

from propulse_core.security.hmac import (
    SIGNATURE_WINDOW_SECONDS,
    new_nonce,
    sign,
    timestamp_ok,
    verify,
)

SECRET = "test-signing-secret"


def test_sign_verify_roundtrip():
    nonce, ts = new_nonce(), int(time.time())
    body = b'{"pulse":"cart_idle"}'
    assert verify(SECRET, ts, nonce, body, sign(SECRET, ts, nonce, body))


def test_body_tampering_fails():
    nonce, ts = new_nonce(), int(time.time())
    sig = sign(SECRET, ts, nonce, b"original")
    assert not verify(SECRET, ts, nonce, b"tampered", sig)


def test_replay_with_different_nonce_fails():
    ts, body = int(time.time()), b"{}"
    sig = sign(SECRET, ts, new_nonce(), body)
    assert not verify(SECRET, ts, new_nonce(), body, sig)


def test_wrong_secret_fails():
    nonce, ts, body = new_nonce(), int(time.time()), b"{}"
    assert not verify("other", ts, nonce, body, sign(SECRET, ts, nonce, body))


def test_timestamp_window():
    now = int(time.time())
    assert timestamp_ok(now)
    assert timestamp_ok(now - SIGNATURE_WINDOW_SECONDS + 1)
    assert not timestamp_ok(now - SIGNATURE_WINDOW_SECONDS - 1)
    assert not timestamp_ok(now + SIGNATURE_WINDOW_SECONDS + 1)


def test_nonces_are_unique():
    assert len({new_nonce() for _ in range(1000)}) == 1000
