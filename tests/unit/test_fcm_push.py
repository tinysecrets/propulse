# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from propulse_core.protocol import EventEnvelope
from propulse_worker.push import FCM_MAX_TTL_SECONDS, FCM_SCOPE, FcmSender, build_fcm_message
from propulse_worker.voice import VoiceDispatcher


class _Credentials:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid
        self.token = "test-access-token"
        self.project_id = "demo-project"
        self.refreshed_with: Any = None

    def refresh(self, request: Any) -> None:
        self.refreshed_with = request
        self.valid = True


class _Response:
    def raise_for_status(self) -> None:
        return None


class _HttpClient:
    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs
        self.call: dict[str, Any] | None = None

    async def __aenter__(self) -> _HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> _Response:
        self.call = {"url": url, "headers": headers, "json": json}
        _HTTP_CALLS.append(self.call)
        return _Response()


_HTTP_CALLS: list[dict[str, Any]] = []


def test_build_fcm_message_coerces_values_and_filters_reserved_keys() -> None:
    message = build_fcm_message(
        "device-token",
        {
            "title": "Hello",
            "speak": True,
            "run_ids": '["run-a","run-b"]',
            "from": "reserved",
            "google.bad": "reserved",
            "gcm.bad": "reserved",
            "collapse_key": "reserved",
            "missing": None,
        },
        priority="urgent",
        ttl_seconds=0,
    )["message"]

    assert message["token"] == "device-token"
    assert message["data"] == {
        "title": "Hello",
        "speak": "True",
        "run_ids": '["run-a","run-b"]',
    }
    assert message["android"] == {"priority": "HIGH", "ttl": "1s"}

    capped = build_fcm_message("t", {}, ttl_seconds=FCM_MAX_TTL_SECONDS * 2)
    assert capped["message"]["android"]["ttl"] == f"{FCM_MAX_TTL_SECONDS}s"


@pytest.mark.asyncio
async def test_fcm_sender_is_a_noop_when_disabled() -> None:
    sender = FcmSender(
        SimpleNamespace(fcm_enabled=False, fcm_service_account_json=""),
        credentials_factory=lambda *_args, **_kwargs: pytest.fail("must not load credentials"),
    )
    assert sender.configured is False
    assert await sender.send("device-token", {"body": "hello"}) is False


@pytest.mark.asyncio
async def test_fcm_sender_refreshes_credentials_and_sends_v1_data_message() -> None:
    _HTTP_CALLS.clear()
    credentials = _Credentials(valid=False)
    request = object()
    settings = SimpleNamespace(
        fcm_enabled=True,
        fcm_project_id="",
        fcm_service_account_json=json.dumps({"project_id": "demo-project"}),
    )

    def credentials_factory(info: dict[str, Any], scopes: list[str]) -> _Credentials:
        assert info["project_id"] == "demo-project"
        assert scopes == [FCM_SCOPE]
        return credentials

    sender = FcmSender(
        settings,
        credentials_factory=credentials_factory,
        request_factory=lambda: request,
        http_client_factory=_HttpClient,
    )

    sent = await sender.send(
        "target-token",
        {"title": "ProPulse", "body": "A cart is idle", "speak": "true"},
        priority="high",
        ttl_seconds=60,
    )

    assert sent is True
    assert credentials.refreshed_with is request
    assert len(_HTTP_CALLS) == 1
    call = _HTTP_CALLS[0]
    assert call["url"] == "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"
    assert call["headers"] == {"Authorization": "Bearer test-access-token"}
    assert call["json"]["message"]["token"] == "target-token"
    assert call["json"]["message"]["data"]["body"] == "A cart is idle"
    assert call["json"]["message"]["android"] == {"priority": "HIGH", "ttl": "60s"}


@pytest.mark.asyncio
async def test_fcm_sender_rejects_malformed_service_account_json() -> None:
    sender = FcmSender(
        SimpleNamespace(
            fcm_enabled=True,
            fcm_project_id="demo-project",
            fcm_service_account_json="{not-json",
        ),
        credentials_factory=lambda *_args, **_kwargs: pytest.fail("JSON should fail first"),
    )
    with pytest.raises(ValueError, match="FCM_SERVICE_ACCOUNT_JSON"):
        await sender.send("device-token", {"body": "hello"})


class _NotificationCollection:
    def __init__(self) -> None:
        self.inserted: dict[str, Any] | None = None
        self.updated: dict[str, Any] | None = None

    async def insert_one(self, document: dict[str, Any]) -> SimpleNamespace:
        self.inserted = document
        return SimpleNamespace(inserted_id="notification-id")

    async def update_one(self, query: dict[str, Any], patch: dict[str, Any]) -> None:
        self.updated = {"query": query, "patch": patch}


class _Store:
    def __init__(self) -> None:
        self.notifications = _NotificationCollection()
        self.events: list[dict[str, Any]] = []
        self.transitions: list[tuple[str, dict[str, Any]]] = []

    def col(self, name: str) -> _NotificationCollection:
        assert name == "notifications"
        return self.notifications

    async def get_device_by_id(self, device_id: str) -> dict[str, Any]:
        assert device_id == "device-1"
        return {"tenant_id": "tenant-1", "push_token": "stored-fcm-token"}

    async def transition_run(self, run_id: str, expected: list[str], patch: dict[str, Any]) -> bool:
        self.transitions.append((run_id, patch))
        return True

    async def emit_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class _Tts:
    async def synthesize(self, text: str, *, voice: str, rate: float) -> SimpleNamespace:
        return SimpleNamespace(
            audio_url="https://media.example.test/audio.mp3", provider="test-tts"
        )


class _Push:
    configured = True

    def __init__(self, sent: bool = True) -> None:
        self.sent = sent
        self.calls: list[dict[str, Any]] = []

    async def send(self, token: str, data: dict[str, object], *, priority: str) -> bool:
        self.calls.append({"token": token, "data": data, "priority": priority})
        return self.sent


@pytest.mark.asyncio
async def test_voice_dispatcher_sends_push_and_records_delivery_status() -> None:
    store = _Store()
    runtime = SimpleNamespace(
        store=store,
        tts=_Tts(),
        settings=SimpleNamespace(fcm_enabled=True),
    )
    dispatcher = VoiceDispatcher(runtime)  # type: ignore[arg-type]
    push = _Push()
    dispatcher.push_sender = push  # type: ignore[assignment]
    event = EventEnvelope(
        type="notify.dispatch",
        tenant_id="tenant-1",
        device_id="device-1",
        trace_id="trace-1",
    )
    items = [
        {
            "evt": event,
            "run_id": "run-a",
            "text": "Your cart is waiting",
            "priority": "high",
            "install_id": "install-1",
            "action": {"title": "Your store", "speak": True, "deeplink": "store://cart"},
        },
        {
            "evt": event,
            "run_id": "run-b",
            "text": "A second reminder",
            "priority": "normal",
            "install_id": "install-1",
            "action": {"speak": False},
        },
    ]

    await dispatcher._dispatch("device-1", items)

    assert len(push.calls) == 1
    assert push.calls[0]["token"] == "stored-fcm-token"
    assert push.calls[0]["priority"] == "high"
    data = push.calls[0]["data"]
    assert data["title"] == "Your store"
    assert data["body"]
    assert data["run_id"] == "run-a"
    assert json.loads(str(data["run_ids"])) == ["run-a", "run-b"]
    assert data["speak"] == "true"
    assert data["deeplink"] == "store://cart"
    assert data["audio_url"] == "https://media.example.test/audio.mp3"
    assert store.notifications.updated is not None
    assert store.notifications.updated["query"] == {"_id": "notification-id"}
    patch = store.notifications.updated["patch"]["$set"]
    assert patch["delivery_status"] == "sent"
    assert isinstance(patch["delivery_updated_at"], float)
    assert store.events[0]["payload"]["push_status"] == "sent"
    assert {run_id for run_id, _ in store.transitions} == {"run-a", "run-b"}


@pytest.mark.asyncio
async def test_voice_dispatcher_does_not_lookup_or_send_push_when_disabled() -> None:
    store = _Store()
    runtime = SimpleNamespace(
        store=store,
        tts=_Tts(),
        settings=SimpleNamespace(fcm_enabled=False),
    )
    dispatcher = VoiceDispatcher(runtime)  # type: ignore[arg-type]
    event = EventEnvelope(type="notify.dispatch", tenant_id="tenant-1", trace_id="trace-1")
    await dispatcher._dispatch(
        "unknown",
        [{"evt": event, "run_id": "run-a", "text": "Hello", "priority": "normal"}],
    )
    assert store.notifications.updated is not None
    assert store.notifications.updated["patch"]["$set"]["delivery_status"] == "disabled"
    assert store.events[0]["payload"]["push_status"] == "disabled"


class _CrossTenantStore(_Store):
    async def get_device_by_id(self, device_id: str) -> dict[str, Any]:
        assert device_id == "device-1"
        return {"tenant_id": "other-tenant", "push_token": "must-not-send"}

    async def get_device(self, tenant_id: str, install_id: str) -> dict[str, Any]:
        assert tenant_id == "tenant-1"
        assert install_id == "install-1"
        return {"tenant_id": tenant_id, "push_token": "tenant-scoped-token"}


@pytest.mark.asyncio
async def test_push_token_lookup_never_uses_another_tenants_device() -> None:
    store = _CrossTenantStore()
    dispatcher = VoiceDispatcher(  # type: ignore[arg-type]
        SimpleNamespace(store=store, tts=_Tts(), settings=SimpleNamespace(fcm_enabled=True))
    )
    event = EventEnvelope(
        type="notify.dispatch",
        tenant_id="tenant-1",
        device_id="device-1",
        payload={"install_id": "install-1"},
    )
    token = await dispatcher._find_push_token("device-1", {"evt": event, "install_id": "install-1"})
    assert token == "tenant-scoped-token"
