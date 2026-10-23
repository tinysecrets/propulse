# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class CheckoutResult:
    url: str
    session_id: str
    mode: str


class BillingAdapter(Protocol):
    enabled: bool

    async def create_subscription_checkout(
        self, *, tenant_id: str, plan: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutResult: ...
    async def create_license_checkout(
        self,
        *,
        tenant_id: str,
        tier: str,
        email: str,
        licensee: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult: ...
    async def create_portal_session(self, customer_id: str, return_url: str) -> str: ...
    async def report_usage(
        self, *, subscription_item_id: str, quantity: int, timestamp: int
    ) -> None: ...
    def parse_webhook(self, payload: bytes, signature: str) -> dict[str, Any]: ...
