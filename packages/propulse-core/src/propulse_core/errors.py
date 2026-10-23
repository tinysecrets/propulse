# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any


class ProPulseError(Exception):
    """Base. `code` is stable and machine-readable; `http_status` maps to the gateway."""

    code = "internal_error"
    http_status = 500
    retryable = False

    def __init__(self, message: str = "", **details: Any) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details

    def to_problem(self, trace_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": f"https://propulse.wah-lah.com/errors/{self.code}",
            "title": self.code.replace("_", " ").title(),
            "status": self.http_status,
            "detail": self.message,
        }
        if trace_id:
            body["trace_id"] = trace_id
        if self.details:
            body["errors"] = self.details
        return body


class ValidationError(ProPulseError):
    code, http_status = "validation_error", 400


class AuthError(ProPulseError):
    code, http_status = "unauthorized", 401


class ForbiddenError(ProPulseError):
    code, http_status = "forbidden", 403


class NotFoundError(ProPulseError):
    code, http_status = "not_found", 404


class ConflictError(ProPulseError):
    code, http_status = "conflict", 409


class QuotaExceeded(ProPulseError):
    """The conversion event. Always carries an upgrade_url."""

    code, http_status = "quota_exceeded", 429

    def __init__(
        self,
        message: str,
        *,
        upgrade_url: str,
        limit: int,
        used: int,
        reset_at: str,
        metric: str = "pulses",
    ) -> None:
        super().__init__(
            message,
            upgrade_url=upgrade_url,
            limit=limit,
            used=used,
            reset_at=reset_at,
            metric=metric,
        )
        self.upgrade_url = upgrade_url
        self.retry_after = None


class RateLimited(ProPulseError):
    code, http_status = "rate_limited", 429

    def __init__(
        self, message: str, *, retry_after_ms: int, limit: int, remaining: int, reset_ms: int
    ) -> None:
        super().__init__(
            message,
            retry_after_ms=retry_after_ms,
            limit=limit,
            remaining=remaining,
            reset_ms=reset_ms,
        )
        self.retry_after = max(1, retry_after_ms // 1000)


class IdempotencyConflict(ConflictError):
    code = "idempotency_conflict"


class InvalidTransition(ConflictError):
    code = "invalid_transition"


class LicenseError(ProPulseError):
    code, http_status = "license_error", 402
