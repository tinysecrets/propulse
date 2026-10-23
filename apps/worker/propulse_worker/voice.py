# SPDX-License-Identifier: AGPL-3.0-or-later
"""TTS synthesis, coalescing, and notification dispatch."""

from __future__ import annotations

import asyncio
import time

import structlog
from propulse_core.coalesce import coalesce
from propulse_core.domain.states import PulseState
from propulse_core.protocol import EventEnvelope
from propulse_worker.runtime import CONSUMER_GROUP, Runtime

log = structlog.get_logger(__name__)

COALESCE_WINDOW_MS = 1500


class VoiceDispatcher:
    def __init__(self, runtime: Runtime) -> None:
        self.rt = runtime
        self._pending: dict[str, list[dict]] = {}

    async def run(self) -> None:
        self.rt.install_signals()
        await self.rt.setup()
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

    async def _dispatch(self, device_key: str, items: list[dict]) -> None:
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
        await self.rt.store.col("notifications").insert_one(
            {
                "run_id": run_id,
                "tenant_id": primary["evt"].tenant_id,
                "device_id": device_key,
                "channel": "push",
                "text": text,
                "audio_url": speech.audio_url,
                "provider": speech.provider,
                "priority": priority,
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

        await self.rt.store.emit_event(
            {
                "meta": {"tenant_id": primary["evt"].tenant_id, "type": "notification"},
                "type": "notification.dispatched",
                "trace_id": primary["evt"].trace_id,
                "payload": {"run_id": run_id, "provider": speech.provider, "coalesced": len(items)},
            }
        )

        # FCM would be called here; the push payload is what the SDK speaks.
        log.info(
            "dispatched",
            run_id=run_id,
            provider=speech.provider,
            chars=len(text),
            coalesced=len(items),
        )


async def main() -> None:
    await VoiceDispatcher(Runtime()).run()


if __name__ == "__main__":
    asyncio.run(main())
