#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import csv
import sys
from pathlib import Path

BLOCKED = ("GPL", "SSPL", "BSL", "Commons Clause", "Elastic License")
ALLOWED_PREFIXES = ("MIT", "Apache", "BSD", "ISC", "PSF", "Python", "MPL", "Unlicense", "CC0")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_dep_licenses.py <licenses.csv>")
        return 2

    offenders: list[str] = []
    with Path(sys.argv[1]).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            license_name = (row.get("License") or "").strip()
            package = (row.get("Name") or "").strip()
            if not license_name:
                continue
            if any(b in license_name for b in BLOCKED):
                offenders.append(f"{package}: {license_name}")
            elif not any(license_name.startswith(p) for p in ALLOWED_PREFIXES):
                offenders.append(f"{package}: {license_name} (unclassified)")

    if offenders:
        print("\n".join(f"  x {o}" for o in offenders))
        print(f"\n{len(offenders)} dependency license issue(s).")
        return 1

    print("  dependency licenses clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
