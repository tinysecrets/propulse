# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class Plan:
    action: str
    text: str
    tool_calls: list[dict[str, Any]]
    tokens: int
    credits: int


class LLMAdapter(Protocol):
    name: str

    async def plan(
        self, *, goal: str, context: dict[str, Any], tools: list[dict[str, Any]]
    ) -> Plan: ...
