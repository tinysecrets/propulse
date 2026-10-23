# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import structlog
from propulse_core.bus.base import DLQ_SUFFIX, Bus
from propulse_core.protocol import ENCODER, EventEnvelope
from redis.asyncio import Redis
from redis.exceptions import ResponseError

log = structlog.get_logger(__name__)

MAXLEN = 1_000_000


class RedisStreamsBus(Bus):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, stream: str, evt: EventEnvelope) -> str:
        msg_id = await self._redis.xadd(
            stream, {"e": ENCODER.encode(evt)}, maxlen=MAXLEN, approximate=True
        )
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)

    async def consume(
        self, stream: str, group: str, consumer: str, batch: int = 50, block_ms: int = 5000
    ) -> list[tuple[str, EventEnvelope]]:
        try:
            res = await self._redis.xreadgroup(
                group, consumer, {stream: ">"}, count=batch, block=block_ms
            )
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                await self.ensure_groups(group, [stream])
                return []
            raise
        return self._decode(res)

    async def reclaim(
        self, stream: str, group: str, consumer: str, min_idle_ms: int = 60000, count: int = 20
    ) -> list[tuple[str, EventEnvelope]]:
        try:
            _cursor, entries, _deleted = await self._redis.xautoclaim(
                stream, group, consumer, min_idle_time=min_idle_ms, start_id="0-0", count=count
            )
        except ResponseError:
            return []
        out: list[tuple[str, EventEnvelope]] = []
        for msg_id, fields in entries:
            if not fields:
                continue
            out.append((self._sid(msg_id), self._evt(fields)))
        return out

    async def ack(self, stream: str, group: str, *ids: str) -> None:
        if ids:
            await self._redis.xack(stream, group, *ids)

    async def dead_letter(self, stream: str, evt: EventEnvelope, reason: str) -> None:
        payload = {"e": ENCODER.encode(evt), "reason": reason}
        await self._redis.xadd(stream + DLQ_SUFFIX, payload, maxlen=100_000, approximate=True)
        log.warning(
            "dead_letter", stream=stream, event_type=evt.type, event_id=evt.id, reason=reason
        )

    async def ensure_groups(self, group: str, streams: list[str]) -> None:
        for stream in streams:
            try:
                await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    async def depth(self, stream: str, group: str) -> int:
        try:
            info = await self._redis.xpending(stream, group)
            return int(info.get("pending", 0)) if isinstance(info, dict) else 0
        except ResponseError:
            return 0

    async def close(self) -> None:
        await self._redis.aclose()

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _sid(raw: bytes | str) -> str:
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    @staticmethod
    def _evt(fields: dict) -> EventEnvelope:
        raw = fields.get(b"e") or fields.get("e")
        return msgspec_decode(raw)

    def _decode(self, res) -> list[tuple[str, EventEnvelope]]:
        out: list[tuple[str, EventEnvelope]] = []
        for _stream, entries in res or []:
            for msg_id, fields in entries:
                out.append((self._sid(msg_id), self._evt(fields)))
        return out


def msgspec_decode(raw: bytes | str) -> EventEnvelope:
    data = raw.encode() if isinstance(raw, str) else raw
    return ENCODER_DECODER.decode(data)


from propulse_core.protocol import DECODER as ENCODER_DECODER  # noqa: E402
