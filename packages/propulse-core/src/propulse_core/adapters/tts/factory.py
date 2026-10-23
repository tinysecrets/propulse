# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any


def make_tts(driver: str, settings: Any) -> Any:
    if driver in ("device", "none"):
        from propulse_core.adapters.tts.device import DeviceTTS

        return DeviceTTS()
    if driver == "piper":
        from propulse_core.adapters.tts.piper import PiperTTS

        return PiperTTS(settings.piper_model_path, settings.storage_path + "/tts")
    raise ValueError(f"unknown TTS_DRIVER={driver!r} (device|piper|none)")
