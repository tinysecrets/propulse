# SPDX-License-Identifier: AGPL-3.0-or-later
"""AGPL-3.0 section 13 compliance surface + commercial buy-out logic."""

from __future__ import annotations

import hashlib
import os
import platform
import time
from dataclasses import dataclass, field
from typing import Any

REPO_URL = "https://github.com/tinysecrets/propulse"
LICENSE_ID = "AGPL-3.0-or-later"
COMMERCIAL_LICENSE_URL = "https://propulse.wah-lah.com/license"

COMMERCIAL_TIERS: dict[str, dict[str, Any]] = {
    "single": {
        "id": "single",
        "name": "Commercial Single-Product Buy-Out",
        "price_usd": 15_000,
        "stripe_price_env": "STRIPE_PRICE_COMMERCIAL_SINGLE",
        "grants": [
            "Use, modify and host the server without AGPL source obligations",
            "Deploy in exactly one commercial product or internal service",
            "Perpetual, non-exclusive, worldwide",
            "Private repository access to propulse-pro",
            "12 months of updates; perpetual fallback license thereafter",
        ],
        "renewal_usd": 3_000,
    },
    "unlimited": {
        "id": "unlimited",
        "name": "Commercial Unlimited Buy-Out",
        "price_usd": 25_000,
        "stripe_price_env": "STRIPE_PRICE_COMMERCIAL_UNLIMITED",
        "grants": [
            "Everything in Single, with no product-count limit",
            "White-label / OEM redistribution rights",
            "Private repository access plus pro module source",
            "Priority security patching (72h SLA)",
            "36 months of updates; perpetual fallback license thereafter",
            "Named engineer contact for architecture review",
        ],
        "renewal_usd": 5_000,
    },
}


def build_commit() -> str:
    return os.environ.get("GIT_SHA") or os.environ.get("SOURCE_COMMIT") or "unknown"


def build_time() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(epoch))) if epoch else "unknown"


@dataclass(slots=True)
class SourceDisclosure:
    """Satisfies AGPL section 13: network users must be offered the source."""

    repo: str = REPO_URL
    license: str = LICENSE_ID
    commit_sha: str = field(default_factory=build_commit)
    build_time: str = field(default_factory=build_time)
    version: str = "1.0.0"
    python: str = field(default_factory=platform.python_version)
    source_archive: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "license": self.license,
            "commit_sha": self.commit_sha,
            "build_time": self.build_time,
            "version": self.version,
            "runtime": f"python {self.python}",
            "source_archive": self.source_archive
            or f"{self.repo}/archive/{self.commit_sha}.tar.gz",
            "notices": {
                "modifications": (
                    "Publish modified server source if you offer ProPulse as a network service."
                ),
                "client_apps": "Your own app is unaffected; SDKs are Apache-2.0.",
                "commercial_option": COMMERCIAL_LICENSE_URL,
                "contact": "licensing@wah-lah.com",
            },
            "generated_at": time.time(),
        }


def source_fingerprint() -> str:
    payload = f"{REPO_URL}:{LICENSE_ID}:{build_commit()}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def is_signed_commercial(license_key: str, *, secret: str = "") -> bool:
    """Offline-verifiable license key: PP-C-<tier>-<expiry>-<sig8>."""
    if not license_key.startswith("PP-C-"):
        return False
    parts = license_key.split("-")
    if len(parts) < 5:
        return False
    tier = parts[2].lower()
    if tier not in COMMERCIAL_TIERS:
        return False
    if not secret:
        return True
    import base64
    import hmac as hmaclib

    body = "-".join(parts[:4])
    expected = base64.urlsafe_b64encode(
        hmaclib.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()[:8]
    return hmaclib.compare_digest(expected, parts[4])


def mint_commercial_key(tier: str, expires_at: int, secret: str) -> str:
    import base64
    import hmac as hmaclib

    body = f"PP-C-{tier.upper()}-{expires_at}"
    sig = base64.urlsafe_b64encode(
        hmaclib.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()[:8]
    return f"{body}-{sig}"


def agreement_text(
    *,
    tier: str,
    licensee: str,
    email: str,
    license_key: str,
    issued_at: float,
    expires_at: float | None = None,
) -> str:
    t = COMMERCIAL_TIERS[tier]
    return f"""WAH-LAH PROPULSE AI — COMMERCIAL LICENSE AGREEMENT
{t["name"]}
Effective {time.strftime("%Y-%m-%d", time.gmtime(issued_at))}

1. PARTIES
   Licensor: Wah-Lah ("Licensor")
   Licensee: {licensee} ("Licensee"), contact {email}
   License key: {license_key}

2. GRANT
   Licensor grants Licensee a perpetual, non-exclusive, non-transferable,
   worldwide right to use, modify, and host the ProPulse AI server software
   identified in section 3, free from the source-disclosure obligations of
   AGPL-3.0 section 13.

3. SCOPE
{chr(10).join(f"   - {g}" for g in t["grants"])}

4. RESTRICTIONS
   - No sublicensing except under OEM terms in the Unlimited tier.
   - Copyright notices must be preserved.
   - Trademark "Wah-Lah" and "ProPulse" usage per TRADEMARK.md.

5. FEES
   One-time fee of USD {t["price_usd"]:,}, paid via Stripe, non-refundable after
   14 days. Optional renewal at USD {t["renewal_usd"]:,}/year for continued updates.

6. DELIVERY
   Private repository access granted via GitHub App within 1 business day of
   payment. License key is delivered immediately and verifies offline.

7. SUPPORT
   Tier-appropriate support per SUPPORT.md.

8. WARRANTY AND LIABILITY
   Software provided "as is". Aggregate liability capped at fees paid.

9. TERM AND TERMINATION
   Perpetual unless materially breached and uncured in 30 days. On termination,
   the then-current release remains licensed in perpetuity.

10. GOVERNING LAW
    Delaware, USA.

Accepted electronically by payment of the invoice.

Licensor: Wah-Lah            Licensee: {licensee}
Signed: /s/ Wah-Lah          Signed: /s/ {licensee}
Date: {time.strftime("%Y-%m-%d", time.gmtime(issued_at))}
"""


def license_id_for(session_id: str) -> str:
    return "lic_" + hashlib.sha256(session_id.encode()).hexdigest()[:20]
