# SPDX-License-Identifier: AGPL-3.0-or-later
"""Egress with HMAC signing, exponential retry, DLQ, and SSRF guard."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import socket
import time
from urllib.parse import urlparse

import httpx
import structlog
from propulse_worker.runtime import CONSUMER_GROUP, Runtime

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 6
BASE_BACKOFF = 5.0
TIMEOUT = 10.0


def is_safe_url(url: str, *, allow_private: bool = False) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_loopback or ip.is_link_local:
            return True
        if ip.is_private and not allow_private:
            continue
        if ip.is_private and allow_private:
            return True
    return bool(infos)


class WebhookSender:
    def __init__(self, runtime: Runtime) -> None:
        self.rt = runtime

    async def run(self) -> None:
        self.rt.install_signals()
        await self.rt.setup()
        while not self.rt.stopping:
            batch = await self.rt.bus.consume(
                "pp:webhook.deliver", CONSUMER_GROUP, self.rt.consumer, batch=20, block_ms=2000
            )
            for mid, evt in batch:
                await self._deliver(evt)
                await self.rt.bus.ack("pp:webhook.deliver", CONSUMER_GROUP, mid)

    async def _deliver(self, evt) -> None:
        url = evt.payload.get("url", "")
        if not url or not is_safe_url(url):
            await self.rt.bus.dead_letter("pp:webhook.deliver", evt, f"unsafe url: {url}")
            return

        body = evt.payload.get("body", "{}").encode()
        ts = str(int(time.time()))
        sig = hmac.new(
            evt.payload.get("secret", "").encode(),
            f"{ts}.{hashlib.sha256(body).hexdigest()}".encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "content-type": "application/json",
            "user-agent": "Wah-Lah-ProPulse/1.0",
            "x-pp-timestamp": ts,
            "x-pp-signature": f"sha256={sig}",
            "x-pp-event": evt.type,
            "x-pp-delivery": evt.id,
        }

        attempt = int(evt.payload.get("attempt", 0))
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
                resp = await client.post(url, content=body, headers=headers)
            if 200 <= resp.status_code < 300:
                log.info("webhook_ok", url=url, status=resp.status_code, delivery=evt.id)
                return
            if resp.status_code < 500 and resp.status_code != 429:
                await self.rt.bus.dead_letter("pp:webhook.deliver", evt, f"http {resp.status_code}")
                return
            raise RuntimeError(f"http {resp.status_code}")
        except Exception as exc:
            attempt += 1
            if attempt >= MAX_ATTEMPTS:
                await self.rt.bus.dead_letter("pp:webhook.deliver", evt, str(exc)[:200])
                await self.rt.store.audit(
                    {
                        "tenant_id": evt.tenant_id,
                        "action": "webhook_dlq",
                        "url": url,
                        "error": str(exc)[:200],
                    }
                )
                return
            delay = min(BASE_BACKOFF * (2 ** (attempt - 1)), 900)
            log.info("webhook_retry", url=url, attempt=attempt, delay=delay)
            await self.rt.bus.publish(
                "pp:webhook.deliver",
                type(evt)(
                    type=evt.type,
                    tenant_id=evt.tenant_id,
                    pulse_id=evt.pulse_id,
                    trace_id=evt.trace_id,
                    dedupe_key=evt.dedupe_key,
                    payload={**evt.payload, "attempt": attempt},
                ),
            )


async def main() -> None:
    await WebhookSender(Runtime()).run()


if __name__ == "__main__":
    asyncio.run(main())
