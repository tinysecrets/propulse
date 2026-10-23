# SPDX-License-Identifier: AGPL-3.0-or-later
"""MongoDB adapter. Uses pymongo.AsyncMongoClient (motor is in maintenance)."""

from __future__ import annotations

import time
from typing import Any

import structlog
from propulse_core.errors import ConflictError
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

log = structlog.get_logger(__name__)


class MongoStore:
    def __init__(self, uri: str, db_name: str = "propulse", *, max_pool_size: int = 20) -> None:
        self._client = AsyncMongoClient(
            uri,
            maxPoolSize=max_pool_size,
            tz_aware=False,
            retryWrites=True,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            appname="propulse",
        )
        self._db = self._client[db_name]

    # --- plumbing ----------------------------------------------------------
    @property
    def db(self):
        return self._db

    def col(self, name: str):
        return self._db[name]

    async def connect(self) -> None:
        await self._client.admin.command("ping")

    async def close(self) -> None:
        await self._client.close()

    async def ping(self) -> bool:
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    async def ensure_indexes(self) -> None:
        d = self._db
        await d.tenants.create_index("slug", unique=True)
        await d.api_keys.create_index("key_id", unique=True)
        await d.api_keys.create_index([("tenant_id", ASCENDING), ("kind", ASCENDING)])
        await d.devices.create_index(
            [("tenant_id", ASCENDING), ("install_id", ASCENDING)], unique=True
        )
        await d.devices.create_index([("tenant_id", ASCENDING), ("last_seen_at", DESCENDING)])
        await d.pulses.create_index([("tenant_id", ASCENDING), ("key", ASCENDING)], unique=True)
        await d.pulses.create_index(
            [("tenant_id", ASCENDING), ("state", ASCENDING), ("ttl_at", ASCENDING)]
        )
        await d.pulse_runs.create_index([("pulse_id", ASCENDING), ("state", ASCENDING)])
        await d.pulse_runs.create_index([("state", ASCENDING), ("lease_at", ASCENDING)])
        await d.pulse_runs.create_index("dedupe_key")
        await d.notifications.create_index([("run_id", ASCENDING)])
        await d.usage_ledger.create_index(
            [("tenant_id", ASCENDING), ("metric", ASCENDING), ("period", ASCENDING)]
        )
        await d.usage_ledger.create_index([("stripe_reported", ASCENDING)])
        await d.subscriptions.create_index("tenant_id", unique=True)
        await d.subscriptions.create_index("stripe_customer_id")
        await d.entitlements.create_index("tenant_id", unique=True)
        await d.stripe_events.create_index("event_id", unique=True)
        await d.licenses.create_index("license_id", unique=True)
        await d.licenses.create_index("stripe_session_id")
        await d.audit_log.create_index([("tenant_id", ASCENDING), ("at", DESCENDING)])
        await d.flags.create_index("key", unique=True)
        await d.webhook_deliveries.create_index(
            [("status", ASCENDING), ("next_retry_at", ASCENDING)]
        )
        # time-series for events
        existing = {c["name"] async for c in await d.list_collections()}
        if "events" not in existing:
            try:
                await d.create_collection(
                    "events",
                    timeseries={"timeField": "ts", "metaField": "meta", "granularity": "seconds"},
                    expireAfterSeconds=60 * 60 * 24 * 90,
                )
            except Exception as exc:  # pragma: no cover - older servers
                log.warning("timeseries_unavailable", error=str(exc))
        log.info("indexes_ensured")

    # --- tenants -----------------------------------------------------------
    async def get_tenant_by_slug(self, slug: str) -> dict[str, Any] | None:
        return await self.col("tenants").find_one({"slug": slug})

    async def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        return await self.col("tenants").find_one({"_id": tenant_id})

    async def upsert_tenant(self, doc: dict[str, Any]) -> str:
        tid = doc.pop("_id", None) or doc["slug"]
        await self.col("tenants").update_one(
            {"_id": tid},
            {"$set": {**doc, "_id": tid}, "$setOnInsert": {"created_at": time.time()}},
            upsert=True,
        )
        return tid

    async def list_tenants(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = self.col("tenants").find().limit(limit)
        return [d async for d in cur]

    # --- api keys ----------------------------------------------------------
    async def create_api_key(self, doc: dict[str, Any]) -> str:
        doc.setdefault("created_at", time.time())
        try:
            res = await self.col("api_keys").insert_one(doc)
        except DuplicateKeyError as exc:
            raise ConflictError("key_id already exists", key_id=doc.get("key_id")) from exc
        return str(res.inserted_id)

    async def get_api_key(self, key_id: str) -> dict[str, Any] | None:
        return await self.col("api_keys").find_one({"key_id": key_id})

    async def list_api_keys(self, tenant_id: str) -> list[dict[str, Any]]:
        cur = self.col("api_keys").find({"tenant_id": tenant_id}).sort("created_at", DESCENDING)
        return [d async for d in cur]

    async def touch_api_key(self, key_id: str, when: float) -> None:
        await self.col("api_keys").update_one({"key_id": key_id}, {"$set": {"last_used_at": when}})

    async def update_api_key(self, key_id: str, patch: dict[str, Any]) -> None:
        await self.col("api_keys").update_one({"key_id": key_id}, {"$set": patch})

    async def revoke_api_key(self, key_id: str, when: float) -> None:
        await self.col("api_keys").update_one(
            {"key_id": key_id}, {"$set": {"revoked_at": when, "active": False}}
        )

    # --- devices -----------------------------------------------------------
    async def upsert_device(self, doc: dict[str, Any]) -> str:
        now = time.time()
        install_id = doc["install_id"]
        tenant_id = doc["tenant_id"]
        res = await self.col("devices").find_one_and_update(
            {"tenant_id": tenant_id, "install_id": install_id},
            {"$set": {**doc, "last_seen_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return str(res["_id"]) if res else ""

    async def get_device(self, tenant_id: str, install_id: str) -> dict[str, Any] | None:
        return await self.col("devices").find_one(
            {"tenant_id": tenant_id, "install_id": install_id}
        )

    async def get_device_by_id(self, device_id: str) -> dict[str, Any] | None:
        from bson import ObjectId

        try:
            return await self.col("devices").find_one({"_id": ObjectId(device_id)})
        except Exception:
            return None

    async def list_devices(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cur = self.col("devices").find({"tenant_id": tenant_id}).limit(limit)
        return [d async for d in cur]

    # --- pulses ------------------------------------------------------------
    async def create_pulse(self, doc: dict[str, Any]) -> str:
        now = time.time()
        doc.setdefault("created_at", now)
        doc["updated_at"] = now
        try:
            res = await self.col("pulses").insert_one(doc)
        except DuplicateKeyError as exc:
            raise ConflictError("pulse key already exists", key=doc.get("key")) from exc
        return str(res.inserted_id)

    async def get_pulse(self, pulse_id: str) -> dict[str, Any] | None:
        from bson import ObjectId

        try:
            return await self.col("pulses").find_one({"_id": ObjectId(pulse_id)})
        except Exception:
            return None

    async def find_pulse(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        return await self.col("pulses").find_one({"tenant_id": tenant_id, "key": key})

    async def list_pulses(
        self, tenant_id: str, *, state: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        q: dict[str, Any] = {"tenant_id": tenant_id}
        if state:
            q["state"] = state
        cur = self.col("pulses").find(q).limit(limit)
        return [d async for d in cur]

    async def update_pulse(self, pulse_id: str, patch: dict[str, Any]) -> None:
        from bson import ObjectId

        patch["updated_at"] = time.time()
        await self.col("pulses").update_one(
            {"_id": ObjectId(pulse_id)}, {"$set": patch, "$inc": {"revision": 1}}
        )

    async def due_pulses(self, now: float, limit: int = 200) -> list[dict[str, Any]]:
        cur = (
            self.col("pulses")
            .find({"state": {"$in": ["armed", "coalescing"]}, "next_fire_at": {"$lte": now}})
            .sort("next_fire_at", ASCENDING)
            .limit(limit)
        )
        return [d async for d in cur]

    # --- runs --------------------------------------------------------------
    async def create_run(self, doc: dict[str, Any]) -> str:
        doc.setdefault("created_at", time.time())
        res = await self.col("pulse_runs").insert_one(doc)
        return str(res.inserted_id)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        from bson import ObjectId

        try:
            return await self.col("pulse_runs").find_one({"_id": ObjectId(run_id)})
        except Exception:
            return None

    async def claim_run(
        self, run_id: str, owner: str, when: float, expected: list[str]
    ) -> dict[str, Any] | None:
        from bson import ObjectId

        return await self.col("pulse_runs").find_one_and_update(
            {
                "_id": ObjectId(run_id),
                "state": {"$in": expected},
                "$or": [
                    {"lease_owner": None},
                    {"lease_at": {"$lt": when - 30}},
                    {"lease_owner": owner},
                ],
            },
            {"$set": {"lease_owner": owner, "lease_at": when}},
            return_document=ReturnDocument.AFTER,
        )

    async def transition_run(self, run_id: str, expected: list[str], patch: dict[str, Any]) -> bool:
        """Conditional transition: duplicate bus delivery becomes a no-op."""
        from bson import ObjectId

        res = await self.col("pulse_runs").update_one(
            {"_id": ObjectId(run_id), "state": {"$in": expected}},
            {"$set": {**patch, "updated_at": time.time()}, "$inc": {"revision": 1}},
        )
        return res.modified_count == 1

    async def update_run(self, run_id: str, patch: dict[str, Any]) -> None:
        from bson import ObjectId

        await self.col("pulse_runs").update_one(
            {"_id": ObjectId(run_id)}, {"$set": {**patch, "updated_at": time.time()}}
        )

    async def list_runs(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cur = (
            self.col("pulse_runs")
            .find({"tenant_id": tenant_id})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [d async for d in cur]

    async def orphan_runs(self, older_than: float, limit: int = 100) -> list[dict[str, Any]]:
        cur = (
            self.col("pulse_runs")
            .find(
                {
                    "state": {"$in": ["planning", "executing", "awaiting_tool", "notifying"]},
                    "lease_at": {"$lt": older_than},
                }
            )
            .limit(limit)
        )
        return [d async for d in cur]

    # --- events ------------------------------------------------------------
    async def emit_event(self, doc: dict[str, Any]) -> None:
        doc.setdefault("ts", time.time())
        doc.setdefault("meta", {})
        await self.col("events").insert_one(doc)

    async def count_events(self, tenant_id: str, since: float) -> int:
        return await self.col("events").count_documents(
            {"meta.tenant_id": tenant_id, "ts": {"$gte": since}}
        )

    # --- entitlements / subscription --------------------------------------
    async def get_entitlements(self, tenant_id: str) -> dict[str, Any] | None:
        return await self.col("entitlements").find_one({"tenant_id": tenant_id})

    async def upsert_entitlements(self, tenant_id: str, doc: dict[str, Any]) -> int:
        res = await self.col("entitlements").find_one_and_update(
            {"tenant_id": tenant_id},
            {
                "$set": {**doc, "tenant_id": tenant_id, "updated_at": time.time()},
                "$inc": {"version": 1},
                "$setOnInsert": {"version": 0},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(res.get("version", 1)) if res else 1

    async def get_subscription(self, tenant_id: str) -> dict[str, Any] | None:
        return await self.col("subscriptions").find_one({"tenant_id": tenant_id})

    async def upsert_subscription(self, tenant_id: str, doc: dict[str, Any]) -> None:
        await self.col("subscriptions").update_one(
            {"tenant_id": tenant_id},
            {"$set": {**doc, "tenant_id": tenant_id, "updated_at": time.time()}},
            upsert=True,
        )

    async def find_subscription_by_customer(self, customer_id: str) -> dict[str, Any] | None:
        return await self.col("subscriptions").find_one({"stripe_customer_id": customer_id})

    # --- usage -------------------------------------------------------------
    async def bump_usage(self, tenant_id: str, metric: str, qty: int, period: str) -> int:
        res = await self.col("usage_ledger").find_one_and_update(
            {"tenant_id": tenant_id, "metric": metric, "period": period},
            {
                "$inc": {"qty": qty},
                "$set": {"updated_at": time.time()},
                "$setOnInsert": {"stripe_reported": False, "created_at": time.time()},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(res["qty"]) if res else qty

    async def get_usage(self, tenant_id: str, metric: str, period: str) -> int:
        doc = await self.col("usage_ledger").find_one(
            {"tenant_id": tenant_id, "metric": metric, "period": period}
        )
        return int(doc["qty"]) if doc else 0

    async def unreported_usage(self, limit: int = 500) -> list[dict[str, Any]]:
        cur = self.col("usage_ledger").find({"stripe_reported": False}).limit(limit)
        return [d async for d in cur]

    async def mark_usage_reported(self, ids: list[str]) -> None:
        from bson import ObjectId

        await self.col("usage_ledger").update_many(
            {"_id": {"$in": [ObjectId(i) for i in ids]}}, {"$set": {"stripe_reported": True}}
        )

    # --- idempotency / audit ----------------------------------------------
    async def claim_stripe_event(self, event_id: str) -> bool:
        try:
            await self.col("stripe_events").insert_one(
                {"event_id": event_id, "at": time.time(), "processed": False}
            )
            return True
        except DuplicateKeyError:
            return False

    async def audit(self, doc: dict[str, Any]) -> None:
        doc.setdefault("at", time.time())
        await self.col("audit_log").insert_one(doc)

    # --- licenses ----------------------------------------------------------
    async def create_license(self, doc: dict[str, Any]) -> str:
        doc.setdefault("created_at", time.time())
        res = await self.col("licenses").insert_one(doc)
        return str(res.inserted_id)

    async def get_license(self, license_id: str) -> dict[str, Any] | None:
        return await self.col("licenses").find_one({"license_id": license_id})

    async def get_license_by_session(self, session_id: str) -> dict[str, Any] | None:
        return await self.col("licenses").find_one({"stripe_session_id": session_id})

    async def update_license(self, license_id: str, patch: dict[str, Any]) -> None:
        await self.col("licenses").update_one(
            {"license_id": license_id}, {"$set": {**patch, "updated_at": time.time()}}
        )

    # --- flags -------------------------------------------------------------
    async def get_flag(self, key: str) -> bool:
        doc = await self.col("flags").find_one({"key": key})
        return bool(doc["value"]) if doc else False

    async def set_flag(self, key: str, value: bool) -> None:
        await self.col("flags").update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": time.time()}},
            upsert=True,
        )

    async def all_flags(self) -> dict[str, bool]:
        return {d["key"]: bool(d["value"]) async for d in self.col("flags").find()}
