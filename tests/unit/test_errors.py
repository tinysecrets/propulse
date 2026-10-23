# SPDX-License-Identifier: AGPL-3.0-or-later
from propulse_core.errors import LicenseError, QuotaExceeded, RateLimited, ValidationError


def test_problem_document_includes_trace_and_details() -> None:
    error = ValidationError("pulse is required", field="pulse")
    problem = error.to_problem("trace-123")
    assert problem["status"] == 400
    assert problem["title"] == "Validation Error"
    assert problem["trace_id"] == "trace-123"
    assert problem["errors"] == {"field": "pulse"}


def test_problem_document_omits_optional_fields_when_absent() -> None:
    problem = ValidationError("bad request").to_problem()
    assert "trace_id" not in problem
    assert "errors" not in problem


def test_quota_and_rate_errors_expose_retry_and_upgrade_details() -> None:
    quota = QuotaExceeded(
        "quota reached",
        upgrade_url="https://example.test/upgrade",
        limit=1000,
        used=1000,
        reset_at="2026-11-01T00:00:00+00:00",
    )
    assert quota.to_problem("trace").get("errors", {}).get("upgrade_url") == (
        "https://example.test/upgrade"
    )
    assert quota.retry_after is None

    limited = RateLimited("slow down", retry_after_ms=2500, limit=60, remaining=0, reset_ms=12345)
    assert limited.retry_after == 2
    assert limited.to_problem()["status"] == 429


def test_license_error_maps_to_payment_required() -> None:
    error = LicenseError("commercial license required")
    assert error.http_status == 402
    assert error.to_problem()["title"] == "License Error"
