# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import sys

from propulse_core.storage.mongo import MongoStore


async def check() -> int:
    from propulse_api.settings import Settings

    s = Settings()
    store = MongoStore(s.mongo_uri, s.mongo_db)
    try:
        await store.connect()
        ok = await store.ping()
    finally:
        await store.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
