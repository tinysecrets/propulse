#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compare two OpenAPI documents. Breaking change => exit 1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

METHODS = {"get", "post", "put", "patch", "delete"}


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def routes(doc: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for path, ops in (doc.get("paths") or {}).items():
        out[path] = {m.upper() for m in ops if m.lower() in METHODS}
    return out


def required_params(doc: dict) -> dict[tuple[str, str], set[str]]:
    out: dict[tuple[str, str], set[str]] = {}
    for path, ops in (doc.get("paths") or {}).items():
        for method, spec in ops.items():
            if method.lower() not in METHODS:
                continue
            names = {p["name"] for p in (spec.get("parameters") or []) if p.get("required")}
            out[(path, method.upper())] = names
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: diff_openapi.py <old.json> <new.json>")
        return 2

    old, new = load(sys.argv[1]), load(sys.argv[2])
    old_routes, new_routes = routes(old), routes(new)
    old_params = required_params(old)
    new_params = required_params(new)

    problems: list[str] = []

    for path, methods in old_routes.items():
        if path not in new_routes:
            problems.append(f"removed path: {path}")
            continue
        for method in methods - new_routes[path]:
            problems.append(f"removed method: {method} {path}")

    for key, names in old_params.items():
        if key in new_params:
            added = new_params[key] - names
            if added:
                problems.append(
                    f"new REQUIRED params on {key[1]} {key[0]}: {sorted(added)} "
                    "(breaking for existing clients)"
                )

    if problems:
        print("\n".join(f"  x {p}" for p in problems))
        print(f"\n{len(problems)} breaking change(s). Update docs/deprecation-policy.md.")
        return 1

    print(f"  contract stable: {len(new_routes)} paths, no breaking change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
