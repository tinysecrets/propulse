# SPDX-License-Identifier: AGPL-3.0-or-later
"""TTS synthesis, coalescing, and notification dispatch."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

import structlog
from propulse_core.coalesce import coalesce
from propulse_core.domain.states import PulseState
from propulse_core.protocol import EventEnvelope

from propulse_worker.push import FcmSender

if TYPE_CHECKING:
    from propulse_worker.runtime import Runtime

log = structlog.get_logger(__name__)

CONSUMER_GROUP = "propulse"
COALESCE_WINDOW_MS = 1500


class VoiceDispatcher:
    def __init__(self, runtime: Runtime) -> None:
        self.rt = runtime
        self._pending: dict[str, list[dict[str, Any]]] = {}
        self.push_sender: FcmSender | None = None

    async def run(self) -> None:
        self.rt.install_signals()
        await self.rt.setup()
        self.push_sender = FcmSender(self.rt.settings)
        while not self.rt.stopping:
            batch = await self.rt.bus.consume(
                "pp:notify.dispatch",
                CONSUMER_GROUP,
                self.rt.consumer,
                batch=20,
                block_ms=COALESCE_WINDOW_MS,
            )
            if not batch:
                await self._flush_all()
                continue
            for mid, evt in batch:
                self._enqueue(evt)
                await self.rt.bus.ack("pp:notify.dispatch", CONSUMER_GROUP, mid)
            await self._flush_all()

    def _enqueue(self, evt: EventEnvelope) -> None:
        key = evt.device_id or evt.payload.get("install_id", "unknown")
        self._pending.setdefault(key, []).append({"evt": evt, **evt.payload})

    async def _flush_all(self) -> None:
        pending, self._pending = self._pending, {}
        for device_key, items in pending.items():
            try:
                await self._dispatch(device_key, items)
            except Exception as exc:
                log.exception("dispatch_failed", device=device_key, error=str(exc))

    async def _dispatch(self, device_key: str, items: list[dict[str, Any]]) -> None:
        items.sort(
            key=lambda i: {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(
                i.get("priority", "normal"), 2
            )
        )

        if len(items) > 1:
            merged = coalesce([i["text"] for i in items])
            text = merged.merged
            primary = items[0]
            log.info(
                "coalesced",
                device=device_key,
                merged_count=merged.count,
                truncated=merged.truncated,
            )
        else:
            text = items[0]["text"]
            primary = items[0]

        speech = await self.rt.tts.synthesize(text, voice="default", rate=1.0)

        run_id = primary["run_id"]
        priority = primary.get("priority", "normal")
        notifications = self.rt.store.col("notifications")
        notification_result = await notifications.insert_one(
            {
                "run_id": run_id,
                "tenant_id": primary["evt"].tenant_id,
                "device_id": device_key,
                "channel": "push",
                "text": text,
                "audio_url": speech.audio_url,
                "provider": speech.provider,
                "priority": priority,
                "delivery_status": "pending",
                "created_at": time.time(),
                "coalesced_count": len(items),
            }
        )

        for item in items:
            await self.rt.store.transition_run(
                str(item["run_id"]),
                [PulseState.NOTIFYING.value, PulseState.PLANNING.value],
                {
                    "state": PulseState.NOTIFYING.value,
                    "delivered_text": text,
                    "audio_url": speech.audio_url,
                },
            )

        push_status = await self._send_push(
            device_key=device_key,
            primary=primary,
            items=items,
            text=text,
            audio_url=speech.audio_url,
            priority=priority,
        )
        if getattr(notification_result, "inserted_id", None) is not None:
            await notifications.update_one(
                {"_id": notification_result.inserted_id},
                {"$set": {"delivery_status": push_status, "delivery_updated_at": time.time()}},
            )

        await self.rt.store.emit_event(
            {
                "meta": {"tenant_id": primary["evt"].tenant_id, "type": "notification"},
                "type": "notification.dispatched",
                "trace_id": primary["evt"].trace_id,
                "payload": {
                    "run_id": run_id,
                    "provider": speech.provider,
                    "coalesced": len(items),
                    "push_status": push_status,
                },
            }
        )

        log.info(
            "dispatched",
            run_id=run_id,
            provider=speech.provider,
            chars=len(text),
            coalesced=len(items),
            push_status=push_status,
        )

    async def _send_push(
        self,
        *,
        device_key: str,
        primary: dict[str, Any],
        items: list[dict[str, Any]],
        text: str,
        audio_url: str | None,
        priority: str,
    ) -> str:
        sender = self.push_sender
        settings = getattr(self.rt, "settings", None)
        if sender is None or not bool(getattr(settings, "fcm_enabled", False)):
            return "disabled"
        if not sender.configured:
            log.warning("fcm_configuration_missing")
            return "configuration_missing"

        token = await self._find_push_token(device_key, primary)
        if not token:
            return "no_token"

        action = primary.get("action")
        action = action if isinstance(action, dict) else {}
        run_ids = list(dict.fromkeys(str(item["run_id"]) for item in items if item.get("run_id")))
        payload: dict[str, object] = {
            "title": str(action.get("title") or "ProPulse"),
            "body": text,
            "run_id": str(primary["run_id"]),
            "run_ids": json.dumps(run_ids, separators=(",", ":")),
            "priority": priority,
            "speak": str(bool(action.get("speak", True))).lower(),
        }
        deeplink = action.get("deeplink")
        if isinstance(deeplink, str) and deeplink:
            payload["deeplink"] = deeplink
        if audio_url:
            payload["audio_url"] = str(audio_url)

        try:
            sent = await sender.send(token, payload, priority=priority)
        except Exception as exc:
            log.warning(
                "fcm_dispatch_failed",
                run_id=str(primary.get("run_id", "")),
                error_type=type(exc).__name__,
            )
            return "failed"
        return "sent" if sent else "disabled"

    async def _find_push_token(self, device_key: str, primary: dict[str, Any]) -> str:
        store = self.rt.store
        device: dict[str, Any] | None = None
        evt = primary.get("evt")
        tenant_id = str(getattr(evt, "tenant_id", ""))
        if device_key and device_key != "unknown":
            lookup = getattr(store, "get_device_by_id", None)
            if lookup is not None:
                try:
                    candidate = await lookup(device_key)
                    if candidate and (
                        not tenant_id or str(candidate.get("tenant_id", "")) == tenant_id
                    ):
                        device = candidate
                    elif candidate:
                        log.warning("fcm_device_tenant_mismatch")
                except Exception as exc:
                    log.warning("fcm_device_lookup_failed", error_type=type(exc).__name__)

        install_id = str(
            primary.get("install_id") or getattr(evt, "payload", {}).get("install_id", "")
        )
        if not device and install_id and tenant_id:
            lookup = getattr(store, "get_device", None)
            if lookup is not None:
                try:
                    device = await lookup(tenant_id, install_id)
                except Exception as exc:
                    log.warning("fcm_device_lookup_failed", error_type=type(exc).__name__)

        return str((device or {}).get("push_token") or "").strip()


async def main() -> None:
    from propulse_worker.runtime import Runtime

    await VoiceDispatcher(Runtime()).run()


if __name__ == "__main__":
    asyncio.run(main())
