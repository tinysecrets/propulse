# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Protocol

from propulse_core.protocol import EventEnvelope

STREAMS = {
    "pulse.triggered": "pp:pulse.triggered",
    "pulse.signal": "pp:pulse.signal",
    "agent.plan": "pp:agent.plan",
    "agent.tool": "pp:agent.tool",
    "voice.synthesize": "pp:voice.synthesize",
    "notify.dispatch": "pp:notify.dispatch",
    "webhook.deliver": "pp:webhook.deliver",
    "run.completed": "pp:run.completed",
}

DLQ_SUFFIX = ".dlq"


class Bus(Protocol):
    async def publish(self, stream: str, evt: EventEnvelope) -> str: ...
    async def consume(
        self, stream: str, group: str, consumer: str, batch: int = 50, block_ms: int = 5000
    ) -> list[tuple[str, EventEnvelope]]: ...
    async def ack(self, stream: str, group: str, *ids: str) -> None: ...
    async def reclaim(
        self, stream: str, group: str, consumer: str, min_idle_ms: int = 60000, count: int = 20
    ) -> list[tuple[str, EventEnvelope]]: ...
    async def dead_letter(self, stream: str, evt: EventEnvelope, reason: str) -> None: ...
    async def ensure_groups(self, group: str, streams: list[str]) -> None: ...
    async def depth(self, stream: str, group: str) -> int: ...
    async def close(self) -> None: ...
