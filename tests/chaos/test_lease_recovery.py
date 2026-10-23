# SPDX-License-Identifier: AGPL-3.0-or-later
"""A crashed worker's run must be reclaimable, never orphaned."""

import time

from propulse_core.domain.states import PulseState

LEASE_SECONDS = 30


class LeaseStore:
    def __init__(self):
        self.runs = {
            "r1": {
                "state": PulseState.PLANNING.value,
                "lease_owner": "worker-a",
                "lease_at": time.time(),
            }
        }

    async def claim_run(self, run_id, owner, when, expected):
        run = self.runs.get(run_id)
        if run is None or run["state"] not in expected:
            return None
        if run["lease_owner"] == owner:
            return run
        if run["lease_at"] < when - LEASE_SECONDS:
            run.update({"lease_owner": owner, "lease_at": when})
            return run
        return None


async def test_live_lease_is_not_stolen():
    store = LeaseStore()
    assert await store.claim_run("r1", "worker-b", time.time(), [PulseState.PLANNING.value]) is None


async def test_expired_lease_is_reclaimed():
    store = LeaseStore()
    store.runs["r1"]["lease_at"] = time.time() - 120
    claimed = await store.claim_run("r1", "worker-b", time.time(), [PulseState.PLANNING.value])
    assert claimed is not None
    assert claimed["lease_owner"] == "worker-b"


async def test_same_owner_can_renew():
    store = LeaseStore()
    assert (
        await store.claim_run("r1", "worker-a", time.time(), [PulseState.PLANNING.value])
        is not None
    )
