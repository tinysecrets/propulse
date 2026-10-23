#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

AGPL_EXPECTED = ("AGPL", "Affero")
APACHE_EXPECTED = ("Apache",)


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
            expected = APACHE_EXPECTED if wheel.name.startswith("propulse_sdk-") else AGPL_EXPECTED
            label = "Apache-2.0" if expected is APACHE_EXPECTED else "AGPL"
            if not any(e in text for e in expected):
                problems.append(f"{wheel.name}: METADATA does not declare {label}")
            if not any("LICENSE" in n for n in zf.namelist()):
                problems.append(f"{wheel.name}: no LICENSE bundled")

    if problems:
        print("\n".join(f"  x {p}" for p in problems))
        return 1

    print(f"  {len(wheels)} wheel(s) declare their expected license and bundle LICENSE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
