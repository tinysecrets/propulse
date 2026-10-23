# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional local neural TTS. Ships in the container, no API key."""

from __future__ import annotations

import asyncio
import hashlib
import pathlib
import shutil

import structlog
from propulse_core.adapters.tts.base import Speech
from propulse_core.adapters.tts.device import DeviceTTS

log = structlog.get_logger(__name__)


class PiperTTS:
    name = "piper"

    def __init__(self, model_path: str, out_dir: str) -> None:
        self._model = model_path
        self._out = pathlib.Path(out_dir)
        self._out.mkdir(parents=True, exist_ok=True)
        self._fallback = DeviceTTS()
        self._available = bool(shutil.which("piper")) and pathlib.Path(model_path).exists()
        if not self._available:
            log.info("piper_unavailable_falling_back_to_device")

    async def synthesize(self, text: str, *, voice: str = "default", rate: float = 1.0) -> Speech:
        key = hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()[:24]
        out = self._out / f"{key}.wav"
        if out.exists():
            return Speech(
                text=text,
                voice=voice,
                rate=rate,
                provider="piper",
                cache_key=key,
                audio_url=f"/media/{out.name}",
            )
        if not self._available:
            return await self._fallback.synthesize(text, voice=voice, rate=rate)

        proc = await asyncio.create_subprocess_exec(
            "piper",
            "--model",
            self._model,
            "--output_file",
            str(out),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate(text.encode())
        if proc.returncode != 0:
            log.warning("piper_failed", error=stderr.decode()[:200])
            return await self._fallback.synthesize(text, voice=voice, rate=rate)
        return Speech(
            text=text,
            voice=voice,
            rate=rate,
            provider="piper",
            cache_key=key,
            audio_url=f"/media/{out.name}",
        )
