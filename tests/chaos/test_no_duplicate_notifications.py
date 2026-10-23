# SPDX-License-Identifier: AGPL-3.0-or-later
"""The invariant that matters: at-least-once must not become at-least-twice."""

from propulse_core.bus.memory import MemoryBus
from propulse_core.domain.states import PulseState
from propulse_core.protocol import EventEnvelope


class FakeStore:
    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.transitions: list[str] = []

    async def get_run(self, run_id):
        return self.runs.get(run_id)

    async def transition_run(self, run_id, expected, patch):
        run = self.runs.get(run_id)
        if run is None or run["state"] not in expected:
            return False
        run.update(patch)
        self.transitions.append("applied")
        return True


async def test_duplicate_delivery_produces_one_side_effect():
    store, bus = FakeStore(), MemoryBus()
    run_id = "r1"
    store.runs[run_id] = {"state": PulseState.TRIGGERED.value}

    evt = EventEnvelope(type="pulse.triggered", payload={"run_id": run_id})
    await bus.publish("pp:pulse.triggered", evt)

    # Simulate the same message delivered three times (XAUTOCLAIM + redelivery).
    for _ in range(3):
        await store.transition_run(
            run_id, [PulseState.TRIGGERED.value], {"state": PulseState.PLANNING.value}
        )

    assert store.transitions.count("applied") == 1
    assert store.runs[run_id]["state"] == PulseState.PLANNING.value


async def test_memory_bus_ack_clears_pending():
    bus = MemoryBus()
    await bus.publish("s", EventEnvelope(type="t"))
    batch = await bus.consume("s", "g", "c")
    assert len(batch) == 1
    await bus.ack("s", "g", batch[0][0])
    assert await bus.depth("s", "g") == 0


async def test_memory_bus_dead_letters():
    bus = MemoryBus()
    await bus.dead_letter("s", EventEnvelope(type="poison"), "boom")
    assert len(bus.dlq["s.dlq"]) == 1
