# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from propulse_core.bus.base import Bus
from propulse_core.bus.memory import MemoryBus
from propulse_core.bus.redis_streams import RedisStreamsBus
from redis.asyncio import Redis


def make_bus(driver: str, redis_url: str = "") -> Bus:
    if driver == "memory":
        return MemoryBus()
    if driver == "redis":
        if not redis_url:
            raise ValueError("REDIS_URL required for BUS_DRIVER=redis")
        return RedisStreamsBus(Redis.from_url(redis_url, decode_responses=False))
    raise ValueError(f"unknown BUS_DRIVER={driver!r} (redis|memory)")
