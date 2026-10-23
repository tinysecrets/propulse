# SPDX-License-Identifier: AGPL-3.0-or-later
"""In-process bus. Zero dependencies — used by unit tests and BUS_DRIVER=memory."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque

from propulse_core.bus.base import DLQ_SUFFIX, Bus
from propulse_core.protocol import EventEnvelope


class MemoryBus(Bus):
    def __init__(self, maxlen: int = 100_000) -> None:
        self._streams: dict[str, deque[tuple[str, EventEnvelope]]] = defaultdict(deque)
        self._dlq: dict[str, list[EventEnvelope]] = defaultdict(list)
        self._pending: dict[tuple[str, str], dict[str, EventEnvelope]] = defaultdict(dict)
        self._seq = 0
        self._maxlen = maxlen
        self._lock = asyncio.Lock()

    async def publish(self, stream: str, evt: EventEnvelope) -> str:
        async with self._lock:
            self._seq += 1
            msg_id = f"{self._seq}-0"
            q = self._streams[stream]
            q.append((msg_id, evt))
            while len(q) > self._maxlen:
                q.popleft()
            return msg_id

    async def consume(
        self, stream: str, group: str, consumer: str, batch: int = 50, block_ms: int = 0
    ) -> list[tuple[str, EventEnvelope]]:
        async with self._lock:
            out: list[tuple[str, EventEnvelope]] = []
            q = self._streams[stream]
            for _ in range(min(batch, len(q))):
                msg_id, evt = q.popleft()
                self._pending[(stream, group)][msg_id] = evt
                out.append((msg_id, evt))
            return out

    async def reclaim(
        self, stream: str, group: str, consumer: str, min_idle_ms: int = 0, count: int = 20
    ) -> list[tuple[str, EventEnvelope]]:
        return []

    async def ack(self, stream: str, group: str, *ids: str) -> None:
        pending = self._pending[(stream, group)]
        for i in ids:
            pending.pop(i, None)

    async def dead_letter(self, stream: str, evt: EventEnvelope, reason: str) -> None:
        self._dlq[stream + DLQ_SUFFIX].append(evt)

    async def ensure_groups(self, group: str, streams: list[str]) -> None:
        for s in streams:
            self._streams.setdefault(s, deque())

    async def depth(self, stream: str, group: str) -> int:
        return len(self._pending[(stream, group)])

    async def close(self) -> None:
        self._streams.clear()
        self._pending.clear()

    @property
    def dlq(self) -> dict[str, list[EventEnvelope]]:
        return self._dlq
