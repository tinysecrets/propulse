# SPDX-License-Identifier: AGPL-3.0-or-later
"""AGPL-3.0 section 13 compliance. The endpoint that sells commercial licenses."""

from __future__ import annotations

from fastapi import APIRouter
from propulse_core.licensing import COMMERCIAL_TIERS, SourceDisclosure, source_fingerprint

router = APIRouter(tags=["license"])


@router.get("/source", summary="AGPL section 13 source disclosure")
async def source() -> dict[str, object]:
    disclosure = SourceDisclosure().to_dict()
    disclosure["fingerprint"] = source_fingerprint()
    return disclosure


@router.get("/v1/license/tiers", summary="Commercial buy-out tiers")
async def tiers() -> dict[str, object]:
    return {
        "currency": "USD",
        "one_time": True,
        "tiers": [
            {
                "id": t["id"],
                "name": t["name"],
                "price_usd": t["price_usd"],
                "renewal_usd": t["renewal_usd"],
                "grants": t["grants"],
            }
            for t in COMMERCIAL_TIERS.values()
        ],
        "checkout_endpoint": "POST /v1/license/checkout",
        "why": (
            "AGPL-3.0 section 13 obliges anyone offering ProPulse as a network "
            "service to publish their modified server source. If you want to keep "
            "your server modifications private, buy a commercial buy-out."
        ),
        "contact": "licensing@wah-lah.com",
    }
