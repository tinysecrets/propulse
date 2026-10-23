# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import sys

from propulse_worker.runtime import Runtime


async def check() -> int:
    rt = Runtime()
    try:
        await rt.setup()
        ok = await rt.store.ping()
        await rt.teardown()
        return 0 if ok else 1
    except Exception as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
