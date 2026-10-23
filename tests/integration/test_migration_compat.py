# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mongo-backed migration compatibility checks; CI provides a disposable MongoDB."""

from __future__ import annotations

import time
import uuid

import pytest
from propulse_core.storage.mongo import MongoStore


@pytest.mark.asyncio
async def test_indexes_are_idempotent_and_legacy_pulses_remain_readable() -> None:
    from propulse_api.settings import Settings

    settings = Settings()
    store = MongoStore(settings.mongo_uri, settings.mongo_db)
    tenant_id = f"migration-{uuid.uuid4().hex}"
    pulse_key = f"legacy-{uuid.uuid4().hex}"
    await store.connect()
    try:
        await store.ensure_indexes()
        await store.ensure_indexes()
        await store.col("tenants").insert_one(
            {"_id": tenant_id, "slug": tenant_id, "name": "Migration test", "plan": "free"}
        )
        # Deliberately omit newer optional fields such as revision, schema_ver and policy.
        await store.col("pulses").insert_one(
            {
                "tenant_id": tenant_id,
                "key": pulse_key,
                "name": "Legacy pulse",
                "state": "registered",
                "trigger": {"kind": "interval", "every_seconds": 900},
                "action": {"kind": "say", "text": "legacy"},
                "next_fire_at": time.time() + 3600,
            }
        )
        found = await store.find_pulse(tenant_id, pulse_key)
        assert found is not None
        assert found["key"] == pulse_key
        assert found.get("policy", {}) == {}
        assert found.get("revision", 1) == 1
    finally:
        await store.col("pulses").delete_many({"tenant_id": tenant_id})
        await store.col("tenants").delete_many({"_id": tenant_id})
        await store.close()
