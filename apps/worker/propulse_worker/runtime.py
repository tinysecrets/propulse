# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared worker runtime: bus, store, adapters, graceful shutdown, lease renewal."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from propulse_core.adapters.llm.factory import make_llm
from propulse_core.adapters.tts.factory import make_tts
from propulse_core.bus.base import STREAMS
from propulse_core.bus.factory import make_bus
from propulse_core.logging import configure_logging
from propulse_core.storage.mongo import MongoStore

log = structlog.get_logger(__name__)

CONSUMER_GROUP = "propulse"


@dataclass(slots=True)
class Runtime:
    consumer: str = field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    store: Any = None
    bus: Any = None
    llm: Any = None
    tts: Any = None
    settings: Any = None
    redis: Any = None
    _stopping: asyncio.Event = field(default_factory=asyncio.Event)

    async def setup(self) -> None:
        from propulse_api.settings import Settings

        self.settings = Settings()
        configure_logging(self.settings.log_level, json_logs=self.settings.is_production)
        self.store = MongoStore(self.settings.mongo_uri, self.settings.mongo_db)
        await self.store.connect()
        self.bus = make_bus(self.settings.bus_driver, self.settings.redis_url)
        await self.bus.ensure_groups(CONSUMER_GROUP, list(STREAMS.values()))
        self.llm = make_llm(self.settings.llm_driver, self.settings)
        self.tts = make_tts(self.settings.tts_driver, self.settings)
        log.info("worker_ready", consumer=self.consumer, llm=self.llm.name, tts=self.tts.name)

    async def teardown(self) -> None:
        with contextlib.suppress(Exception):
            await self.bus.close()
        with contextlib.suppress(Exception):
            await self.store.close()

    @property
    def stopping(self) -> bool:
        return self._stopping.is_set()

    def install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._stopping.set)

    async def sleep(self, seconds: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)


async def renew_lease(
    store: Any, run_id: str, owner: str, stop: asyncio.Event, interval: float = 10.0
) -> None:
    while not stop.is_set():
        await asyncio.sleep(interval)
        try:
            await store.update_run(run_id, {"lease_at": time.time(), "lease_owner": owner})
        except Exception:
            log.warning("lease_renew_failed", run_id=run_id)
