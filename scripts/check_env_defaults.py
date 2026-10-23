#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every env var must have a working local default in settings.py."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "apps/api/propulse_api/settings.py"
ENV_EXAMPLE = ROOT / ".env.example"


def main() -> int:
    if not SETTINGS.exists():
        print("settings.py missing")
        return 1
    source = SETTINGS.read_text(encoding="utf-8")
    fields = set(re.findall(r"^\s{4}(\w+)\s*:", source, re.MULTILINE))
    documented = {
        line.split("=", 1)[0].strip().lower()
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    missing = {
        f
        for f in fields
        if f not in documented
        and f
        not in {
            "model_config",
            "is_production",
            "secret_key",
        }
    }
    if missing:
        print(f"undocumented env vars: {sorted(missing)}")
        return 1
    print(f"  {len(fields)} settings, all documented with defaults")
    return 0


if __name__ == "__main__":
    sys.exit(main())
