# SPDX-License-Identifier: AGPL-3.0-or-later
"""Consumes pulse.triggered, drives the FSM, hands off to the agent."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from propulse_core.domain.states import PulseState, advance
from propulse_core.protocol import EventEnvelope

from propulse_worker.runtime import CONSUMER_GROUP, Runtime, renew_lease

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 5
LEASE_SECONDS = 30


class Orchestrator:
    def __init__(self, runtime: Runtime) -> None:
        self.rt = runtime

    async def run(self) -> None:
        self.rt.install_signals()
        await self.rt.setup()
        reclaim = asyncio.create_task(self._reclaim_loop())
        try:
            while not self.rt.stopping:
                batch = await self.rt.bus.consume(
                    "pp:pulse.triggered", CONSUMER_GROUP, self.rt.consumer, batch=25, block_ms=2000
                )
                if not batch:
                    continue
                await asyncio.gather(
                    *(self._handle(mid, evt) for mid, evt in batch), return_exceptions=True
                )
        finally:
            reclaim.cancel()
            await self.rt.teardown()

    async def _reclaim_loop(self) -> None:
        while not self.rt.stopping:
            try:
                stale = await self.rt.bus.reclaim(
                    "pp:pulse.triggered", CONSUMER_GROUP, self.rt.consumer, min_idle_ms=60_000
                )
                for mid, evt in stale:
                    log.info("reclaimed", event_id=evt.id)
                    await self._handle(mid, evt)
            except Exception as exc:
                log.warning("reclaim_error", error=str(exc))
            await asyncio.sleep(30)

    async def _handle(self, msg_id: str, evt: EventEnvelope) -> None:
        run_id = evt.payload.get("run_id", "")
        if not run_id:
            await self.rt.bus.ack("pp:pulse.triggered", CONSUMER_GROUP, msg_id)
            return

        run = await self.rt.store.get_run(run_id)
        if run is None:
            await self.rt.bus.ack("pp:pulse.triggered", CONSUMER_GROUP, msg_id)
            return

        if run["state"] in {
            s.value
            for s in (
                PulseState.COMPLETED,
                PulseState.SUPPRESSED,
                PulseState.FAILED_TERMINAL,
                PulseState.EXPIRED,
            )
        }:
            await self.rt.bus.ack("pp:pulse.triggered", CONSUMER_GROUP, msg_id)
            return

        owner = f"{self.rt.consumer}:{run_id[:8]}"
        claimed = await self.rt.store.claim_run(
            run_id,
            owner,
            time.time(),
            [
                PulseState.COALESCING.value,
                PulseState.ARMED.value,
                PulseState.FAILED_RETRYABLE.value,
            ],
        )
        if claimed is None:
            await self.rt.bus.ack("pp:pulse.triggered", CONSUMER_GROUP, msg_id)
            return

        stop = asyncio.Event()
        lease = asyncio.create_task(renew_lease(self.rt.store, run_id, owner, stop))

        try:
            await self._drive(run, evt)
            await self.rt.bus.ack("pp:pulse.triggered", CONSUMER_GROUP, msg_id)
        except Exception as exc:
            await self._on_error(run, evt, exc)
        finally:
            stop.set()
            lease.cancel()

    async def _drive(self, run: dict[str, Any], evt: EventEnvelope) -> None:
        run_id = str(run["_id"])
        policy = run.get("policy") or {}

        # 1. Coalescing window: merge siblings, then fire once.
        await self._transition(
            run_id, PulseState.COALESCING, PulseState.TRIGGERED, {"triggered_at": time.time()}
        )

        # 2. Quiet hours
        if self._in_quiet_hours(policy) and policy.get("priority") not in ("urgent", "high"):
            await self._transition(
                run_id,
                PulseState.TRIGGERED,
                PulseState.SUPPRESSED,
                {"suppressed_reason": "quiet_hours"},
            )
            return

        # 3. Daily cap
        if await self._over_daily_cap(run):
            await self._transition(
                run_id,
                PulseState.TRIGGERED,
                PulseState.SUPPRESSED,
                {"suppressed_reason": "daily_cap"},
            )
            return

        await self._transition(run_id, PulseState.TRIGGERED, PulseState.PLANNING, {})
        await self.rt.bus.publish(
            "pp:agent.plan",
            EventEnvelope(
                type="agent.plan.requested",
                tenant_id=evt.tenant_id,
                pulse_id=evt.pulse_id,
                device_id=evt.device_id,
                trace_id=evt.trace_id,
                dedupe_key=evt.dedupe_key,
                payload={"run_id": run_id, **evt.payload},
            ),
        )
        log.info("handed_off_to_agent", run_id=run_id, pulse=run.get("pulse_key"))

    async def _transition(
        self, run_id: str, current: PulseState, target: PulseState, extra: dict[str, Any]
    ) -> None:
        advance(current, target)
        ok = await self.rt.store.transition_run(
            run_id, [current.value], {"state": target.value, **extra}
        )
        if not ok:
            log.debug("transition_noop", run_id=run_id, current=current.value)

    def _in_quiet_hours(self, policy: dict[str, Any]) -> bool:
        start, end = policy.get("quiet_hours_start"), policy.get("quiet_hours_end")
        if start is None or end is None:
            return False
        hour = time.localtime().tm_hour
        return bool(hour >= start or hour < end if start > end else start <= hour < end)

    async def _over_daily_cap(self, run: dict[str, Any]) -> bool:
        cap = int((run.get("policy") or {}).get("max_per_day", 5))
        since = time.time() - 86_400
        count = await self.rt.store.col("notifications").count_documents(
            {"tenant_id": run["tenant_id"], "ack_at": {"$gte": since}}
        )
        return bool(count >= cap)

    async def _on_error(self, run: dict[str, Any], evt: EventEnvelope, exc: Exception) -> None:
        run_id = str(run["_id"])
        attempts = int(run.get("attempts", 0)) + 1
        log.warning("run_failed", run_id=run_id, attempts=attempts, error=str(exc))

        if attempts >= MAX_ATTEMPTS:
            await self.rt.store.update_run(
                run_id,
                {
                    "state": PulseState.FAILED_TERMINAL.value,
                    "attempts": attempts,
                    "last_error": str(exc)[:500],
                },
            )
            await self.rt.bus.dead_letter("pp:pulse.triggered", evt, str(exc)[:200])
            return

        await self.rt.store.update_run(
            run_id,
            {
                "state": PulseState.FAILED_RETRYABLE.value,
                "attempts": attempts,
                "last_error": str(exc)[:500],
            },
        )
        backoff = min(2**attempts, 60)
        await asyncio.sleep(backoff)
        await self.rt.bus.publish(
            "pp:pulse.triggered",
            EventEnvelope(
                type="pulse.retry",
                tenant_id=evt.tenant_id,
                pulse_id=evt.pulse_id,
                trace_id=evt.trace_id,
                dedupe_key=evt.dedupe_key,
                payload=evt.payload,
            ),
        )


async def main() -> None:
    await Orchestrator(Runtime()).run()


if __name__ == "__main__":
    asyncio.run(main())
