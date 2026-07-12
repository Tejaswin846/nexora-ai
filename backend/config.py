from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    env: str = Field(
        "development",
        validation_alias=AliasChoices("NEXORA_ENV", "SOFTWARE_ENV", "ENV"),
    )
    app_name: str = Field("Nexora Agent", validation_alias="NEXORA_APP_NAME")
    app_version: str = Field("10.15.0-main-layered-memory-quality", validation_alias="NEXORA_VERSION")
    public_app_url: str = Field("", validation_alias="NEXORA_PUBLIC_APP_URL")
    allowed_origins: str = Field(
        "",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "SOFTWARE_ALLOWED_ORIGINS"),
    )
    database_url: str = Field("", validation_alias=AliasChoices("DATABASE_URL", "SUPABASE_DB_URL"))
    supabase_url: str = Field("", validation_alias="SUPABASE_URL")
    supabase_anon_key: str = Field("", validation_alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field("", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    upstash_redis_rest_url: str = Field("", validation_alias="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field("", validation_alias="UPSTASH_REDIS_REST_TOKEN")
    jwt_secret: str = Field("", validation_alias=AliasChoices("JWT_SECRET", "NEXORA_AUTH_SECRET"))
    clerk_secret_key: str = Field("", validation_alias="CLERK_SECRET_KEY")
    clerk_publishable_key: str = Field("", validation_alias="CLERK_PUBLISHABLE_KEY")
    clerk_jwt_issuer: str = Field("", validation_alias="CLERK_JWT_ISSUER")
    clerk_webhook_secret: str = Field("", validation_alias="CLERK_WEBHOOK_SECRET")
    log_level: str = Field("INFO", validation_alias="NEXORA_LOG_LEVEL")
    request_log_sample_rate: float = Field(1.0, validation_alias="REQUEST_LOG_SAMPLE_RATE")
    data_dir: str = Field("backend/nexora_data", validation_alias="NEXORA_DATA_DIR")
    posthog_api_key: str = Field("", validation_alias=AliasChoices("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY"))
    posthog_public_key: str = Field(
        "",
        validation_alias=AliasChoices("POSTHOG_PROJECT_API_KEY", "POSTHOG_API_KEY", "POSTHOG_PUBLIC_KEY"),
    )
    posthog_host: str = Field("https://us.i.posthog.com", validation_alias="POSTHOG_HOST")
    posthog_enabled: bool = Field(True, validation_alias="POSTHOG_ENABLED")
    posthog_ai_observability_enabled: bool = Field(True, validation_alias="POSTHOG_AI_OBSERVABILITY_ENABLED")
    posthog_session_recording_enabled: bool = Field(True, validation_alias="POSTHOG_SESSION_RECORDING_ENABLED")
    posthog_capture_prompts: bool = Field(False, validation_alias="POSTHOG_CAPTURE_PROMPTS")
    posthog_capture_responses: bool = Field(False, validation_alias="POSTHOG_CAPTURE_RESPONSES")
    posthog_privacy_mode: bool = Field(True, validation_alias="POSTHOG_PRIVACY_MODE")

    @property
    def normalized_env(self) -> str:
        return (self.env or "development").strip().lower()

    @property
    def is_development(self) -> bool:
        return self.normalized_env in {"development", "test"}

    @property
    def is_production(self) -> bool:
        return self.normalized_env == "production"

    @property
    def is_production_like(self) -> bool:
        return self.normalized_env in {"production", "staging"}

    @property
    def cors_allowed_origins(self) -> List[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    def production_missing_variables(self) -> List[str]:
        missing: List[str] = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        elif "/rest/v1" in self.supabase_url.rstrip("/"):
            missing.append("SUPABASE_URL without /rest/v1/")
        if not (self.supabase_service_role_key or self.supabase_anon_key):
            missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
        if not self.database_url:
            missing.append("DATABASE_URL or SUPABASE_DB_URL")
        return missing

    def database_is_sqlite(self) -> bool:
        value = (self.database_url or "").strip().lower()
        return value.startswith("sqlite:") or value.endswith(".sqlite") or value.endswith(".sqlite3")

    def validate_startup(self) -> None:
        if self.is_production:
            missing = self.production_missing_variables()
            if missing:
                raise RuntimeError(f"Production configuration is incomplete. Missing: {', '.join(missing)}.")
        if self.is_production_like and self.database_is_sqlite():
            raise RuntimeError("SQLite database URLs are only allowed in development or test.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
