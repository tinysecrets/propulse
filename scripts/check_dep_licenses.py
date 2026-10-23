#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import csv
import sys
from pathlib import Path

BLOCKED = (
    "GPL",
    "GNU GENERAL PUBLIC LICENSE",
    "SSPL",
    "SERVER SIDE PUBLIC LICENSE",
    "BSL",
    "BUSINESS SOURCE LICENSE",
    "COMMONS CLAUSE",
    "ELASTIC LICENSE",
)
ALLOWED_PREFIXES = (
    "MIT",
    "Apache",
    "BSD",
    "3-Clause BSD License",
    "ISC",
    "PSF",
    "Python",
    "MPL",
    "Mozilla Public License",
    "Unlicense",
    "The Unlicense",
    "CC0",
)
WORKSPACE_PACKAGES = {
    "propulse-api",
    "propulse-worker",
    "propulse-sched",
    "propulse-core",
    "propulse-sdk",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_dep_licenses.py <licenses.csv>")
        return 2

    offenders: list[str] = []
    with Path(sys.argv[1]).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            license_name = (row.get("License") or "").strip()
            package = (row.get("Name") or "").strip()
            # Local workspace projects have their own REUSE/license-boundary checks;
            # this audit is for third-party dependencies only.
            if package.lower() in WORKSPACE_PACKAGES:
                continue
            if not license_name:
                continue
            normalized = license_name.upper()
            if any(b in normalized for b in BLOCKED):
                offenders.append(f"{package}: {license_name}")
            elif not any(normalized.startswith(p.upper()) for p in ALLOWED_PREFIXES):
                offenders.append(f"{package}: {license_name} (unclassified)")

    if offenders:
        print("\n".join(f"  x {o}" for o in offenders))
        print(f"\n{len(offenders)} dependency license issue(s).")
        return 1

    print("  dependency licenses clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
