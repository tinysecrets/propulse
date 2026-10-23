# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plan/act loop with hard time and credit budgets. Deterministic replay."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from propulse_core.domain.states import PulseState
from propulse_core.protocol import EventEnvelope

from propulse_worker.runtime import CONSUMER_GROUP, Runtime

log = structlog.get_logger(__name__)

TOOLS: dict[str, dict[str, Any]] = {
    "get_cart": {"schema": {"type": "object"}, "cost": 2, "timeout": 3},
    "apply_discount": {
        "schema": {"type": "object", "properties": {"pct": {"type": "integer"}}},
        "cost": 3,
        "timeout": 5,
    },
    "get_calendar": {"schema": {"type": "object"}, "cost": 2, "timeout": 3},
    "send_email": {"schema": {"type": "object"}, "cost": 1, "timeout": 8},
}


class Agent:
    def __init__(self, runtime: Runtime) -> None:
        self.rt = runtime

    async def run(self) -> None:
        self.rt.install_signals()
        await self.rt.setup()
        while not self.rt.stopping:
            batch = await self.rt.bus.consume(
                "pp:agent.plan", CONSUMER_GROUP, self.rt.consumer, batch=10, block_ms=2000
            )
            for mid, evt in batch:
                await self._handle(mid, evt)

    async def _handle(self, msg_id: str, evt: EventEnvelope) -> None:
        run_id = evt.payload.get("run_id", "")
        run = await self.rt.store.get_run(run_id) if run_id else None
        if run is None:
            await self.rt.bus.ack("pp:agent.plan", CONSUMER_GROUP, msg_id)
            return

        try:
            await self._plan_and_act(run, evt)
        except Exception as exc:
            log.exception("agent_failed", run_id=run_id)
            await self.rt.store.transition_run(
                run_id,
                [PulseState.PLANNING.value],
                {"state": PulseState.FAILED_RETRYABLE.value, "last_error": str(exc)[:500]},
            )
        finally:
            await self.rt.bus.ack("pp:agent.plan", CONSUMER_GROUP, msg_id)

    async def _plan_and_act(self, run: dict[str, Any], evt: EventEnvelope) -> None:
        run_id = str(run["_id"])
        policy = run.get("policy") or {}
        budget_ms = int(policy.get("budget_ms", 8000))
        budget_credits = int(policy.get("budget_credits", 50))
        deadline = time.monotonic() + budget_ms / 1000
        credits_used = 0

        pulse = await self.rt.store.get_pulse(run["pulse_id"]) or {}
        action = pulse.get("action") or {"kind": "say", "text": pulse.get("name", "Update")}

        context = {
            "text": action.get("text", ""),
            "vars": {**(run.get("trigger") or {}), **(run.get("device_state") or {})},
            "pulse_key": run.get("pulse_key"),
            "tenant_id": run["tenant_id"],
        }

        async with asyncio.timeout(budget_ms / 1000):
            plan = await self.rt.llm.plan(
                goal=action.get("text", "notify the user"),
                context=context,
                tools=[{"name": n, **spec} for n, spec in TOOLS.items()],
            )
            credits_used += plan.credits

            tool_io: list[dict[str, Any]] = []
            for call in plan.tool_calls:
                if credits_used >= budget_credits or time.monotonic() >= deadline:
                    break
                name = call.get("tool", "")
                if name not in TOOLS:
                    continue
                spec = TOOLS[name]
                credits_used += int(spec["cost"])
                try:
                    result = await asyncio.wait_for(
                        self._invoke(name, call.get("args", {}), run),
                        timeout=float(spec["timeout"]),
                    )
                except Exception as exc:
                    result = {"error": str(exc)[:200]}
                tool_io.append(
                    {
                        "tool": name,
                        "args": call.get("args", {}),
                        "result": result,
                        "at": time.time(),
                    }
                )

        await self.rt.store.update_run(
            run_id,
            {
                "tool_io": tool_io,
                "plan_text": plan.text,
                "tokens_used": plan.tokens,
                "credits_used": credits_used,
            },
        )

        text = plan.text or action.get("text", "")
        await self.rt.store.transition_run(
            run_id,
            [PulseState.PLANNING.value],
            {"state": PulseState.NOTIFYING.value, "planned_text": text},
        )
        await self.rt.bus.publish(
            "pp:notify.dispatch",
            EventEnvelope(
                type="notify.dispatch",
                tenant_id=evt.tenant_id,
                pulse_id=evt.pulse_id,
                device_id=evt.device_id,
                trace_id=evt.trace_id,
                dedupe_key=evt.dedupe_key,
                payload={
                    "run_id": run_id,
                    "text": text,
                    "priority": policy.get("priority", "normal"),
                    "action": action,
                    "install_id": run.get("install_id", ""),
                },
            ),
        )
        log.info(
            "agent_completed",
            run_id=run_id,
            credits=credits_used,
            tools=len(tool_io),
            ms=int(budget_ms - (deadline - time.monotonic()) * 1000),
        )

    async def _invoke(self, name: str, args: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
        """Deterministic local implementations. Swap for HTTP tools via registry."""
        if name == "get_cart":
            return {"items": 2, "value_usd": 84.0, "idle_minutes": 16}
        if name == "apply_discount":
            pct = int(args.get("pct", 10))
            return {"applied_pct": pct, "code": f"COMEBACK{pct}"}
        if name == "get_calendar":
            return {"next_event": "Standup", "in_minutes": 5}
        if name == "send_email":
            return {"queued": True, "to": args.get("to", "")}
        return {}


async def main() -> None:
    await Agent(Runtime()).run()


if __name__ == "__main__":
    asyncio.run(main())
