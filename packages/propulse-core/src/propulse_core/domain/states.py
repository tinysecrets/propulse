# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pulse lifecycle state machine. Pure, dependency-free, property-tested."""

from __future__ import annotations

from enum import StrEnum

from propulse_core.errors import InvalidTransition


class PulseState(StrEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    ARMED = "armed"
    COALESCING = "coalescing"
    TRIGGERED = "triggered"
    PLANNING = "planning"
    EXECUTING = "executing"
    AWAITING_TOOL = "awaiting_tool"
    NOTIFYING = "notifying"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    SUPPRESSED = "suppressed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    EXPIRED = "expired"


TERMINAL: frozenset[PulseState] = frozenset(
    {PulseState.COMPLETED, PulseState.SUPPRESSED, PulseState.FAILED_TERMINAL, PulseState.EXPIRED}
)

ACTIVE: frozenset[PulseState] = frozenset(
    {
        PulseState.ARMED,
        PulseState.COALESCING,
        PulseState.TRIGGERED,
        PulseState.PLANNING,
        PulseState.EXECUTING,
        PulseState.AWAITING_TOOL,
        PulseState.NOTIFYING,
        PulseState.FAILED_RETRYABLE,
        PulseState.SNOOZED,
    }
)

TRANSITIONS: dict[PulseState, frozenset[PulseState]] = {
    PulseState.DRAFT: frozenset({PulseState.REGISTERED, PulseState.EXPIRED}),
    PulseState.REGISTERED: frozenset({PulseState.ARMED, PulseState.EXPIRED, PulseState.SUPPRESSED}),
    PulseState.ARMED: frozenset(
        {
            PulseState.COALESCING,
            PulseState.TRIGGERED,
            PulseState.EXPIRED,
            PulseState.SUPPRESSED,
            PulseState.SNOOZED,
        }
    ),
    PulseState.COALESCING: frozenset(
        {
            PulseState.TRIGGERED,
            PulseState.SUPPRESSED,
            PulseState.EXPIRED,
            PulseState.FAILED_RETRYABLE,
        }
    ),
    PulseState.TRIGGERED: frozenset(
        {
            PulseState.PLANNING,
            PulseState.SUPPRESSED,
            PulseState.FAILED_RETRYABLE,
            PulseState.EXPIRED,
        }
    ),
    PulseState.PLANNING: frozenset(
        {
            PulseState.EXECUTING,
            PulseState.NOTIFYING,
            PulseState.SUPPRESSED,
            PulseState.FAILED_RETRYABLE,
            PulseState.FAILED_TERMINAL,
        }
    ),
    PulseState.EXECUTING: frozenset(
        {
            PulseState.AWAITING_TOOL,
            PulseState.NOTIFYING,
            PulseState.COMPLETED,
            PulseState.FAILED_RETRYABLE,
            PulseState.FAILED_TERMINAL,
            PulseState.SUPPRESSED,
        }
    ),
    PulseState.AWAITING_TOOL: frozenset(
        {
            PulseState.EXECUTING,
            PulseState.FAILED_RETRYABLE,
            PulseState.FAILED_TERMINAL,
            PulseState.SUPPRESSED,
        }
    ),
    PulseState.NOTIFYING: frozenset(
        {
            PulseState.COMPLETED,
            PulseState.SNOOZED,
            PulseState.FAILED_RETRYABLE,
            PulseState.FAILED_TERMINAL,
        }
    ),
    PulseState.SNOOZED: frozenset({PulseState.ARMED, PulseState.EXPIRED}),
    PulseState.FAILED_RETRYABLE: frozenset(
        {PulseState.PLANNING, PulseState.FAILED_TERMINAL, PulseState.EXPIRED}
    ),
    PulseState.COMPLETED: frozenset(),
    PulseState.SUPPRESSED: frozenset(),
    PulseState.FAILED_TERMINAL: frozenset(),
    PulseState.EXPIRED: frozenset(),
}


def can_transition(current: PulseState, target: PulseState) -> bool:
    return target in TRANSITIONS[current]


def advance(current: PulseState, target: PulseState) -> PulseState:
    if not can_transition(current, target):
        raise InvalidTransition(
            f"{current} -> {target} is not allowed",
            current=current.value,
            target=target.value,
            allowed=sorted(s.value for s in TRANSITIONS[current]),
        )
    return target


def is_terminal(state: PulseState) -> bool:
    return state in TERMINAL
