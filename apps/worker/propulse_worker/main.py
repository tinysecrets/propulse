# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-role worker entrypoint: WORKER_ROLE=orchestrator|agent|voice|webhook|all"""

from __future__ import annotations

import asyncio
import os
import signal
import sys

from propulse_core.logging import configure_logging


async def run_role(role: str) -> None:
    if role == "orchestrator":
        from propulse_worker.orchestrator import Orchestrator
        from propulse_worker.runtime import Runtime

        await Orchestrator(Runtime()).run()
    elif role == "agent":
        from propulse_worker.agent import Agent
        from propulse_worker.runtime import Runtime

        await Agent(Runtime()).run()
    elif role == "voice":
        from propulse_worker.runtime import Runtime
        from propulse_worker.voice import VoiceDispatcher

        await VoiceDispatcher(Runtime()).run()
    elif role == "webhook":
        from propulse_worker.runtime import Runtime
        from propulse_worker.webhooks import WebhookSender

        await WebhookSender(Runtime()).run()
    else:
        raise SystemExit(f"unknown WORKER_ROLE={role!r}")


def main() -> int:
    role = os.environ.get("WORKER_ROLE", "orchestrator")
    configure_logging(
        os.environ.get("LOG_LEVEL", "info"), json_logs=os.environ.get("ENV", "local") == "prod"
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop = asyncio.Event()

    def _stop(*_):
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        with __import__("contextlib").suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop)

    try:
        loop.run_until_complete(run_role(role))
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
