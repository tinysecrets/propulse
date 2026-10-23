# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class Speech:
    text: str
    voice: str
    rate: float
    audio_url: str = ""
    content_type: str = "audio/wav"
    cache_key: str = ""
    provider: str = "device"


class TTSAdapter(Protocol):
    name: str

    async def synthesize(
        self, text: str, *, voice: str = "default", rate: float = 1.0
    ) -> Speech: ...
