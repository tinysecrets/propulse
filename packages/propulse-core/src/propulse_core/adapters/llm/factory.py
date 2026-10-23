# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any


def make_llm(driver: str, settings: Any) -> Any:
    if driver == "echo":
        from propulse_core.adapters.llm.echo import EchoLLM

        return EchoLLM()
    if driver == "ollama":
        from propulse_core.adapters.llm.ollama import OllamaLLM

        return OllamaLLM(settings.llm_base_url)
    raise ValueError(f"unknown LLM_DRIVER={driver!r} (echo|ollama)")
