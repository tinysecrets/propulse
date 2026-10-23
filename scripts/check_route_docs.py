#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_PREFIX = ("/v1/",)
EXEMPT = ("/healthz", "/readyz", "/metrics", "/openapi.json", "/docs", "/redoc")


def main() -> int:
    spec = json.loads(Path("docs/openapi.json").read_text(encoding="utf-8"))
    missing: list[str] = []

    for path, ops in (spec.get("paths") or {}).items():
        if not any(path.startswith(p) for p in REQUIRED_PREFIX) or path in EXEMPT:
            continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            if not op.get("summary"):
                missing.append(f"{method.upper()} {path}")

    if missing:
        print("\n".join(f"  x undocumented: {m}" for m in missing))
        return 1

    print("  every public route has a summary")
    return 0


if __name__ == "__main__":
    sys.exit(main())
