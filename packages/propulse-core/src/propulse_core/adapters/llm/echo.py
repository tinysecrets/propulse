# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic, offline, zero-cost planner. Used by default and in tests."""

from __future__ import annotations

from typing import Any

from propulse_core.adapters.llm.base import Plan


class EchoLLM:
    name = "echo"

    async def plan(
        self, *, goal: str, context: dict[str, Any], tools: list[dict[str, Any]]
    ) -> Plan:
        template = context.get("text") or goal
        rendered = template
        for key, value in (context.get("vars") or {}).items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        tool_calls = [{"tool": t["name"], "args": {}} for t in tools[:2]]
        return Plan(
            action="say",
            text=rendered,
            tool_calls=tool_calls,
            tokens=len(rendered.split()),
            credits=len(tool_calls),
        )
