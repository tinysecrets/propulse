# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # core
    secret_key: str = Field(default="")
    env: str = "local"
    log_level: str = "info"
    public_base_url: str = "http://localhost:8080"
    upgrade_url: str = "https://propulse.wah-lah.com/upgrade"
    commercial_license_url: str = "https://propulse.wah-lah.com/license"
    source_repo_url: str = "https://github.com/tinysecrets/propulse"

    # storage
    mongo_uri: str = "mongodb://mongo:27017/propulse"
    mongo_db: str = "propulse"
    mongo_max_pool_size: int = 20
    redis_url: str = "redis://redis:6379/0"
    bus_driver: str = "redis"
    storage_driver: str = "fs"
    storage_path: str = "/var/lib/propulse/media"

    # billing
    billing_driver: str = "null"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""
    stripe_price_commercial_single: str = ""
    stripe_price_commercial_unlimited: str = ""

    # ai
    llm_driver: str = "echo"
    llm_base_url: str = "http://ollama:11434"
    llm_max_tokens_per_tenant_per_day: int = 200_000
    tts_driver: str = "device"
    piper_model_path: str = "/opt/piper/en_US-amy-medium.onnx"

    # limits
    rate_limit_free: int = 60
    rate_limit_pro: int = 600
    rate_limit_team: int = 3_000
    rate_limit_fail_open: bool = True
    free_monthly_pulses: int = 1_000
    pro_monthly_pulses: int = 50_000
    team_monthly_pulses: int = 500_000

    # flags
    global_kill: bool = False
    flag_compound_triggers: bool = True
    flag_predictive_send_time: bool = False

    # observability
    otel_enabled: bool = False
    telemetry_enabled: bool = True

    # license
    license_signing_secret: str = ""

    @field_validator("secret_key")
    @classmethod
    def _check_secret(cls, v: str) -> str:
        if not v:
            return secrets.token_urlsafe(32)
        return v

    @property
    def is_production(self) -> bool:
        return self.env in ("prod", "production")

    def rate_limit_for(self, plan: str) -> int:
        return {
            "free": self.rate_limit_free,
            "pro": self.rate_limit_pro,
            "team": self.rate_limit_team,
            "enterprise": self.rate_limit_team * 4,
        }.get(plan, self.rate_limit_free)


settings = Settings()
