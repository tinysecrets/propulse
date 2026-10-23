# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.coalesce import coalesce, should_coalesce


def test_single_text():
    assert coalesce(["Hello"]).merged == "Hello."


def test_two_texts_merge_with_joiner():
    out = coalesce(["Cart is idle", "Meeting in 5"])
    assert out.count == 2
    assert "meeting in 5" in out.merged
    assert out.merged.startswith("Cart is idle. Also,")


def test_respects_char_cap():
    out = coalesce(["A" * 100, "B" * 100, "C" * 100], max_chars=150)
    assert out.truncated >= 1
    assert "more" in out.merged
    assert len(out.merged) <= 200


def test_empty_input():
    assert coalesce([]).merged == ""
    assert coalesce(["", "  "]).merged == ""


def test_should_coalesce_window():
    assert should_coalesce(5, 20)
    assert not should_coalesce(25, 20)
