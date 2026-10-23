# SPDX-License-Identifier: AGPL-3.0-or-later
"""Merge bursts of pulses into one utterance. Biggest perceived-quality win."""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_UTTERANCE_CHARS = 220
JOINERS = ("Also, ", "And, ", "One more: ")


@dataclass(slots=True)
class Coalesced:
    texts: list[str] = field(default_factory=list)
    merged: str = ""
    count: int = 0
    truncated: int = 0


def coalesce(texts: list[str], *, max_chars: int = MAX_UTTERANCE_CHARS) -> Coalesced:
    cleaned = [t.strip().rstrip(".") for t in texts if t and t.strip()]
    if not cleaned:
        return Coalesced()
    if len(cleaned) == 1:
        return Coalesced(texts=cleaned, merged=cleaned[0] + ".", count=1)

    parts: list[str] = [cleaned[0]]
    truncated = 0
    for i, text in enumerate(cleaned[1:], start=1):
        joiner = JOINERS[min(i - 1, len(JOINERS) - 1)]
        candidate = f"{joiner}{text[0].lower()}{text[1:]}"
        if len(". ".join([*parts, candidate])) > max_chars:
            truncated += 1
            continue
        parts.append(candidate)

    merged = ". ".join(parts) + "."
    if truncated:
        merged += f" Plus {truncated} more."
    return Coalesced(texts=cleaned, merged=merged, count=len(parts), truncated=truncated)


def should_coalesce(seconds_since_first: float, window: int) -> bool:
    return seconds_since_first < window
