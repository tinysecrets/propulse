# SPDX-License-Identifier: AGPL-3.0-or-later
from itertools import pairwise

import pytest
from propulse_core.domain.states import (
    ACTIVE,
    TERMINAL,
    TRANSITIONS,
    PulseState,
    advance,
    can_transition,
    is_terminal,
)
from propulse_core.errors import InvalidTransition

ALL = list(PulseState)


def test_every_state_has_transitions_defined():
    assert set(TRANSITIONS) == set(ALL)


def test_terminal_states_have_no_exits():
    for state in TERMINAL:
        assert TRANSITIONS[state] == frozenset()


def test_terminal_and_active_are_disjoint():
    assert not (TERMINAL & ACTIVE)


def test_advance_returns_target():
    assert advance(PulseState.DRAFT, PulseState.REGISTERED) is PulseState.REGISTERED


def test_advance_rejects_illegal():
    with pytest.raises(InvalidTransition):
        advance(PulseState.DRAFT, PulseState.NOTIFYING)


@pytest.mark.parametrize("src", ALL)
@pytest.mark.parametrize("dst", ALL)
def test_transition_table_is_self_consistent(src, dst):
    assert can_transition(src, dst) == (dst in TRANSITIONS[src])


def test_happy_path_is_walkable():
    path = [
        PulseState.DRAFT,
        PulseState.REGISTERED,
        PulseState.ARMED,
        PulseState.COALESCING,
        PulseState.TRIGGERED,
        PulseState.PLANNING,
        PulseState.EXECUTING,
        PulseState.NOTIFYING,
        PulseState.COMPLETED,
    ]
    for src, dst in pairwise(path):
        assert can_transition(src, dst), f"{src} -> {dst}"


def test_retry_loop_is_walkable():
    for src, dst in [
        (PulseState.EXECUTING, PulseState.FAILED_RETRYABLE),
        (PulseState.FAILED_RETRYABLE, PulseState.PLANNING),
        (PulseState.FAILED_RETRYABLE, PulseState.FAILED_TERMINAL),
    ]:
        assert can_transition(src, dst)


def test_snooze_loop_is_walkable():
    assert can_transition(PulseState.NOTIFYING, PulseState.SNOOZED)
    assert can_transition(PulseState.SNOOZED, PulseState.ARMED)


def test_is_terminal():
    assert is_terminal(PulseState.COMPLETED)
    assert not is_terminal(PulseState.ARMED)
