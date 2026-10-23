# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from unittest.mock import Mock

import httpx
import pytest
from propulse_sdk.client import ProPulse, ProPulseError, QuotaExceeded


def _response(status: int = 200, payload: dict | None = None, content: bytes | None = None):
    request = httpx.Request("GET", "https://api.example.test/")
    if content is not None:
        return httpx.Response(status, content=content, request=request)
    return httpx.Response(status, json=payload or {"ok": True}, request=request)


def test_constructor_and_context_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ProPulseError) as error:
        ProPulse("")
    assert error.value.code == "config"
    assert error.value.status == 0

    client = ProPulse("pp_pub_test", base_url="https://api.example.test///")
    assert client._base == "https://api.example.test"
    close = Mock()
    monkeypatch.setattr(client, "close", close)
    with client as entered:
        assert entered is client
    close.assert_called_once_with()


def test_all_public_sdk_methods_make_expected_signed_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ProPulse("pp_pub_test", secret="test-secret", base_url="https://api.example.test/")
    results = [
        {"accepted": True},
        {"device_id": "dev_1"},
        {"ok": True},
        {"pulse_id": "pulse_1"},
        {"plan": "free"},
        {"url": "https://example.test/checkout"},
        {"repo": "https://github.com/tinysecrets/propulse"},
    ]
    request = Mock(side_effect=[_response(payload=p) for p in results])
    monkeypatch.setattr(client._client, "request", request)

    assert client.signal("cart_idle") == results[0]
    assert client.register_device("install-1") == results[1]
    assert client.ack("run-1") == results[2]
    assert client.create_pulse("cart_idle", {"kind": "signal"}) == results[3]
    assert client.entitlements() == results[4]
    assert client.upgrade_url() == results[5]["url"]
    assert client.source_disclosure() == results[6]

    calls = request.call_args_list
    assert len(calls) == 7
    assert [(call.args[0], call.args[1].removeprefix(client._base)) for call in calls] == [
        ("POST", "/v1/pulses:signal"),
        ("POST", "/v1/devices/register"),
        ("POST", "/v1/pulses/ack"),
        ("POST", "/v1/pulses"),
        ("GET", "/v1/billing/entitlements"),
        ("POST", "/v1/billing/checkout"),
        ("GET", "/source"),
    ]
    headers = calls[0].kwargs["headers"]
    assert headers["x-pp-key"] == "pp_pub_test"
    assert headers["x-pp-sig"]
    assert headers["x-pp-protocol"] == "3"
    assert headers["content-type"] == "application/json"
    client.close()


def test_sdk_maps_quota_and_http_errors_and_accepts_empty_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ProPulse("pp_pub_test")
    request = Mock(
        side_effect=[
            _response(
                429,
                {
                    "detail": "monthly quota exceeded",
                    "upgrade_url": "https://example.test/upgrade",
                    "limit": 1000,
                    "used": 1000,
                },
            ),
            _response(400, {"detail": "bad request", "title": "invalid_request"}),
            _response(429, {"detail": "slow down"}),
            _response(204, content=b""),
        ]
    )
    monkeypatch.setattr(client._client, "request", request)

    with pytest.raises(QuotaExceeded) as quota:
        client.signal("cart_idle")
    assert quota.value.upgrade_url == "https://example.test/upgrade"
    assert (quota.value.limit, quota.value.used) == (1000, 1000)

    with pytest.raises(ProPulseError) as bad_request:
        client.signal("cart_idle")
    assert bad_request.value.status == 400
    assert bad_request.value.code == "invalid_request"
    assert bad_request.value.body["detail"] == "bad request"

    with pytest.raises(ProPulseError) as rate_limited:
        client.signal("cart_idle")
    assert rate_limited.value.status == 429
    assert rate_limited.value.code == "error"

    assert client._request("GET", "/empty") == {}
    client.close()
