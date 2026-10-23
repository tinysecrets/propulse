#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail CI if the open-core license boundary is crossed."""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOUNDARIES = {
    "packages/propulse-pro": {
        "allowed": {"propulse_core.api", "propulse_core.protocol", "propulse_core.domain"},
        "forbidden_prefix": "propulse_core.",
    },
    "packages/sdk-python": {
        "allowed": set(),
        "forbidden_prefix": ("propulse_core.", "propulse_pro."),
    },
}
VIOLATIONS: list[str] = []


def main() -> int:
    for rel, rule in BOUNDARIES.items():
        base = ROOT / rel
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                VIOLATIONS.append(f"{py}: syntax error: {exc}")
                continue
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for mod in mods:
                    if not any(
                        mod.startswith(prefix)
                        for prefix in (
                            rule["forbidden_prefix"]
                            if isinstance(rule["forbidden_prefix"], tuple)
                            else (rule["forbidden_prefix"],)
                        )
                    ):
                        continue
                    if any(mod == a or mod.startswith(a + ".") for a in rule["allowed"]):
                        continue
                    VIOLATIONS.append(
                        f"{py.relative_to(ROOT)}:{node.lineno} imports {mod!r} "
                        f"across the {rel} license boundary"
                    )
    if VIOLATIONS:
        print("\n".join(f"  x {v}" for v in VIOLATIONS))
        return 1
    print("  license boundaries clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
