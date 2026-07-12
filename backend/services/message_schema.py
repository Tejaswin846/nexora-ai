from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|_)(authorization|cookie|password|passwd|secret|token|api_key|connection_string)($|_)",
    re.IGNORECASE,
)


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(SENSITIVE_KEY_PATTERN.search(str(key)) or _contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class WorkflowJobMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1", pattern=r"^1$")
    job_id: UUID
    correlation_id: UUID
    organization_id: str
    project_id: str
    job_type: str
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("organization_id", "project_id", "job_type")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        clean = value.strip()
        if not IDENTIFIER_PATTERN.fullmatch(clean):
            raise ValueError("must use letters, numbers, underscores, or hyphens")
        return clean

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def reject_sensitive_message_data(self) -> "WorkflowJobMessage":
        if _contains_sensitive_key(self.payload) or _contains_sensitive_key(self.metadata):
            raise ValueError("queue messages must not contain credentials or raw secrets")
        return self
