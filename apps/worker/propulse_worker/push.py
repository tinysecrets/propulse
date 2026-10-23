# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional Firebase Cloud Messaging HTTP v1 transport."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, cast

import httpx
import structlog

log = structlog.get_logger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_BASE_URL = "https://fcm.googleapis.com/v1/projects"
FCM_MAX_TTL_SECONDS = 2_419_200


def build_fcm_message(
    token: str,
    data: dict[str, object],
    priority: str = "normal",
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Build an FCM data message; data values are strings as required by FCM v1."""
    safe_data = {
        str(key): str(value)
        for key, value in data.items()
        if value is not None
        and str(key).lower() not in {"from", "message_type", "collapse_key"}
        and not str(key).lower().startswith(("google.", "gcm."))
    }
    high_priority = priority.lower() in {"urgent", "high"}
    ttl = max(1, min(int(ttl_seconds), FCM_MAX_TTL_SECONDS))
    return {
        "message": {
            "token": token,
            "data": safe_data,
            "android": {
                "priority": "HIGH" if high_priority else "NORMAL",
                "ttl": f"{ttl}s",
            },
        }
    }


class FcmSender:
    """Send pushes only when enabled and configured; never logs credential contents."""

    def __init__(
        self,
        settings: Any,
        *,
        credentials_factory: Callable[..., Any] | None = None,
        request_factory: Callable[[], Any] | None = None,
        http_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._credentials_factory = credentials_factory
        self._request_factory = request_factory
        self._http_client_factory = http_client_factory or httpx.AsyncClient
        self._credentials: Any = None
        self._project_id = str(getattr(settings, "fcm_project_id", "") or "")
        self._auth_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(
            getattr(self.settings, "fcm_enabled", False)
            and getattr(self.settings, "fcm_service_account_json", "")
        )

    async def send(
        self,
        token: str,
        data: dict[str, object],
        *,
        priority: str = "normal",
        ttl_seconds: int = 3600,
    ) -> bool:
        if not token or not self.configured:
            return False

        credentials = await self._get_credentials()
        project_id = self._project_id or str(getattr(credentials, "project_id", "") or "")
        if not project_id:
            log.error("fcm_missing_project_id")
            return False

        url = f"{FCM_BASE_URL}/{project_id}/messages:send"
        headers = {"Authorization": f"Bearer {credentials.token}"}
        message = build_fcm_message(token, data, priority, ttl_seconds)
        async with self._http_client_factory(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=message)
            response.raise_for_status()

        log.info("fcm_sent", project_id=project_id, priority=priority)
        return True

    async def _get_credentials(self) -> Any:
        async with self._auth_lock:
            if self._credentials is None:
                account_json = str(self.settings.fcm_service_account_json)
                try:
                    info = json.loads(account_json)
                except json.JSONDecodeError as exc:
                    raise ValueError("FCM_SERVICE_ACCOUNT_JSON must contain valid JSON") from exc
                if not isinstance(info, dict):
                    raise ValueError("FCM service account JSON must be an object")

                if self._credentials_factory is not None:
                    self._credentials = self._credentials_factory(info, scopes=[FCM_SCOPE])
                else:
                    from google.oauth2 import service_account

                    credentials_class = cast(Any, service_account.Credentials)
                    self._credentials = credentials_class.from_service_account_info(
                        info, scopes=[FCM_SCOPE]
                    )
                self._project_id = self._project_id or str(info.get("project_id", ""))

            if not self._credentials.valid:
                if self._request_factory is not None:
                    request = self._request_factory()
                else:
                    from google.auth.transport.requests import Request

                    request = Request()
                await asyncio.to_thread(self._credentials.refresh, request)

            return self._credentials
