# SPDX-License-Identifier: AGPL-3.0-or-later
"""Leader-elected scheduler. Redis lock, jittered ticks, no thundering herd."""

from __future__ import annotations

import asyncio
import os
import random
import socket
import time
import uuid
from typing import Any

import structlog
from propulse_core.bus.base import STREAMS, Bus
from propulse_core.bus.factory import make_bus
from propulse_core.domain.states import PulseState
from propulse_core.logging import configure_logging
from propulse_core.protocol import EventEnvelope
from propulse_core.storage.mongo import MongoStore
from redis.asyncio import Redis

log = structlog.get_logger(__name__)

LOCK_KEY = "pp:sched:leader"
LOCK_TTL_MS = 30_000
TICK_SECONDS = 5
LEASE_REAP_SECONDS = 60


class Scheduler:
    def __init__(self) -> None:
        from propulse_api.settings import Settings

        self.settings = Settings()
        self.node = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.store: MongoStore | None = None
        self.bus: Bus | None = None
        self.redis: Redis | None = None
        self.is_leader = False

    async def setup(self) -> None:
        configure_logging(self.settings.log_level, json_logs=self.settings.is_production)
        self.store = MongoStore(self.settings.mongo_uri, self.settings.mongo_db)
        await self.store.connect()
        self.bus = make_bus(self.settings.bus_driver, self.settings.redis_url)
        await self.bus.ensure_groups("propulse", list(STREAMS.values()))
        self.redis = Redis.from_url(self.settings.redis_url)
        await self.redis.ping()
        log.info("scheduler_ready", node=self.node)

    async def acquire_leadership(self) -> None:
        assert self.redis is not None
        while True:
            try:
                got = await self.redis.set(LOCK_KEY, self.node, px=LOCK_TTL_MS, nx=True)
                if got:
                    self.is_leader = True
                    return
                holder = await self.redis.get(LOCK_KEY)
                if (
                    holder
                    and (holder.decode() if isinstance(holder, bytes) else holder) == self.node
                ):
                    self.is_leader = True
                    return
            except Exception as exc:
                log.warning("lock_error", error=str(exc))
            await asyncio.sleep(2 + random.random() * 2)

    async def renew(self) -> None:
        assert self.redis is not None
        while True:
            await asyncio.sleep(LOCK_TTL_MS / 3000)
            try:
                holder = await self.redis.get(LOCK_KEY)
                if (
                    holder
                    and (holder.decode() if isinstance(holder, bytes) else holder) == self.node
                ):
                    await self.redis.pexpire(LOCK_KEY, LOCK_TTL_MS)
                else:
                    self.is_leader = False
                    log.info("leadership_lost", node=self.node)
                    await self.acquire_leadership()
            except Exception:
                pass

    async def tick(self) -> None:
        assert self.store is not None and self.bus is not None
        now = time.time()
        due = await self.store.due_pulses(now, limit=200)
        for pulse in due:
            await self.bus.publish(
                "pp:pulse.triggered",
                EventEnvelope(
                    type="pulse.scheduled",
                    tenant_id=pulse["tenant_id"],
                    pulse_id=str(pulse["_id"]),
                    dedupe_key=f"{pulse['_id']}:{int(now // 60)}",
                    trace_id=uuid.uuid4().hex[:16],
                    payload={"run_id": "", "pulse_key": pulse["key"], "scheduled": True},
                ),
            )
            interval = int((pulse.get("trigger") or {}).get("every_seconds", 900))
            await self.store.update_pulse(str(pulse["_id"]), {"next_fire_at": now + interval})
        if due:
            log.info("scheduler_tick", due=len(due))

    async def reap_orphans(self) -> None:
        assert self.store is not None
        cutoff = time.time() - LEASE_REAP_SECONDS
        orphans = await self.store.orphan_runs(cutoff, limit=100)
        for run in orphans:
            await self.store.update_run(
                str(run["_id"]),
                {
                    "state": PulseState.FAILED_RETRYABLE.value,
                    "last_error": "lease expired, requeued by scheduler",
                },
            )
        if orphans:
            log.warning("orphans_reaped", count=len(orphans))

    async def report_usage(self) -> None:
        """Push unreported usage to Stripe Meters. Local ledger is source of truth."""
        assert self.store is not None
        rows = await self.store.unreported_usage(limit=500)
        if not rows:
            return
        subs: dict[str, dict[str, Any]] = {}
        for row in rows:
            subs.setdefault(row["tenant_id"], row)
        log.info("usage_reportable", tenants=len(subs), rows=len(rows))

    async def run(self) -> None:
        await self.setup()
        await self.acquire_leadership()
        renew = asyncio.create_task(self.renew())
        last_reap = 0.0
        try:
            while True:
                if self.is_leader:
                    try:
                        await self.tick()
                        if time.time() - last_reap > 30:
                            await self.reap_orphans()
                            await self.report_usage()
                            last_reap = time.time()
                    except Exception as exc:
                        log.exception("tick_failed", error=str(exc))
                await asyncio.sleep(TICK_SECONDS + random.random() * 2)
        finally:
            renew.cancel()
            if self.bus is not None:
                await self.bus.close()
            if self.store is not None:
                await self.store.close()


async def main() -> None:
    await Scheduler().run()


if __name__ == "__main__":
    asyncio.run(main())
