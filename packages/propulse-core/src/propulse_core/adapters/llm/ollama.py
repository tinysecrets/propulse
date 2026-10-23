# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from propulse_core.adapters.llm.base import Plan

log = structlog.get_logger(__name__)

SYSTEM = (
    "You are ProPulse, a proactive mobile assistant. Given a goal and context, "
    'return STRICT JSON: {"action":"say","text":"<=120 chars, spoken aloud",'
    '"tool_calls":[{"tool":"name","args":{}}]}. No markdown.'
)


class OllamaLLM:
    name = "ollama"

    def __init__(self, base_url: str, model: str = "llama3.2:3b", timeout: float = 20.0) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def plan(
        self, *, goal: str, context: dict[str, Any], tools: list[dict[str, Any]]
    ) -> Plan:
        prompt = json.dumps({"goal": goal, "context": context, "tools": tools})
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base}/api/generate",
                json={
                    "model": self._model,
                    "system": SYSTEM,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw = data.get("response", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("ollama_bad_json", raw=raw[:200])
            parsed = {"action": "say", "text": goal, "tool_calls": []}

        tokens = int(data.get("eval_count", 0)) + int(data.get("prompt_eval_count", 0))
        return Plan(
            action=parsed.get("action", "say"),
            text=parsed.get("text", goal)[:200],
            tool_calls=parsed.get("tool_calls", []),
            tokens=tokens,
            credits=1 + len(parsed.get("tool_calls", [])),
        )
