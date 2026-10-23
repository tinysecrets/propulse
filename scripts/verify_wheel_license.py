#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

EXPECTED = ("AGPL", "Affero")


def main() -> int:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        print("no wheels found")
        return 1

    problems: list[str] = []
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as zf:
            metadata = next((n for n in zf.namelist() if n.endswith("METADATA")), None)
            if metadata is None:
                problems.append(f"{wheel.name}: no METADATA")
                continue
            text = zf.read(metadata).decode("utf-8", "replace")
            if not any(e in text for e in EXPECTED):
                problems.append(f"{wheel.name}: METADATA does not declare AGPL")
            if not any("LICENSE" in n for n in zf.namelist()):
                problems.append(f"{wheel.name}: no LICENSE bundled")

    if problems:
        print("\n".join(f"  x {p}" for p in problems))
        return 1

    print(f"  {len(wheels)} wheel(s) declare AGPL and bundle LICENSE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
