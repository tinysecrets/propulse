# SPDX-License-Identifier: AGPL-3.0-or-later
"""Default: let the phone speak. Zero server cost, zero latency, offline."""

from __future__ import annotations

import hashlib

from propulse_core.adapters.tts.base import Speech


class DeviceTTS:
    name = "device"

    async def synthesize(self, text: str, *, voice: str = "default", rate: float = 1.0) -> Speech:
        key = hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()[:24]
        return Speech(
            text=text, voice=voice, rate=rate, provider="device", cache_key=key, audio_url=""
        )
