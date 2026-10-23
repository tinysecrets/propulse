# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from propulse_core.entitlements import EntitlementService
from propulse_core.errors import ForbiddenError


@dataclass(slots=True)
class Principal:
    tenant_id: str
    key_id: str
    kind: str
    scopes: frozenset[str]
    plan: str
    auth_method: str = "key"

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise ForbiddenError(
                f"missing scope {scope!r}", required=scope, granted=sorted(self.scopes)
            )


def get_state(request: Request) -> Any:
    return request.app.state


def get_store(request: Request) -> Any:
    return request.app.state.store


def get_bus(request: Request) -> Any:
    return request.app.state.bus


def get_redis(request: Request) -> Any:
    return request.app.state.redis


def get_billing(request: Request) -> Any:
    return request.app.state.billing


def get_entitlements(request: Request) -> EntitlementService:
    return cast(EntitlementService, request.app.state.entitlements)


def get_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise ForbiddenError("no authenticated principal")
    return cast(Principal, principal)


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


Store = Annotated[Any, Depends(get_store)]
Bus = Annotated[Any, Depends(get_bus)]
Redis = Annotated[Any, Depends(get_redis)]
Billing = Annotated[Any, Depends(get_billing)]
Entitlements = Annotated[EntitlementService, Depends(get_entitlements)]
Auth = Annotated[Principal, Depends(get_principal)]
TraceId = Annotated[str, Depends(get_trace_id)]
