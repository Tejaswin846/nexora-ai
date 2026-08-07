from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "1.0"
VALIDATOR_VERSION = "contract-validator-v1"
ENGINE_VERSION = "reliability-engine-v1"
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|[_-])(authorization|cookie|password|passwd|secret|token|api[_-]?key|connection[_-]?string|credential)($|[_-])",
    re.IGNORECASE,
)


class StringEnum(str, Enum):
    pass


class Severity(StringEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StepType(StringEnum):
    MODEL_GENERATION = "MODEL_GENERATION"
    READ_ONLY_API = "READ_ONLY_API"
    DATABASE_READ = "DATABASE_READ"
    DATABASE_WRITE = "DATABASE_WRITE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    INTERNAL_STATE_CHANGE = "INTERNAL_STATE_CHANGE"


class DecisionAction(StringEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CORRECT_AND_RETRY = "CORRECT_AND_RETRY"
    FALLBACK = "FALLBACK"
    ROLLBACK = "ROLLBACK"
    ESCALATE = "ESCALATE"
    TERMINATE = "TERMINATE"


class RecoveryAction(StringEnum):
    NONE = "NONE"
    CORRECT_OUTPUT = "CORRECT_OUTPUT"
    RETRY = "RETRY"
    FALLBACK = "FALLBACK"
    ROLLBACK = "ROLLBACK"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RecoveryStatus(StringEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DUPLICATE = "DUPLICATE"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(timezone.utc)


def validate_identifier(value: str, field_name: str) -> str:
    clean = (value or "").strip()
    if not clean or not IDENTIFIER_PATTERN.fullmatch(clean):
        raise ValueError(f"{field_name} must be a tenant-safe identifier")
    return clean


def redact_for_hash(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "<max-depth>"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            key_text = str(key)
            if SENSITIVE_KEY_PATTERN.search(key_text):
                redacted[key_text] = "<redacted>"
            else:
                redacted[key_text] = redact_for_hash(item, depth + 1)
        return redacted
    if isinstance(value, list):
        return [redact_for_hash(item, depth + 1) for item in value[:200]]
    if isinstance(value, str):
        return value[:4096]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1024]


def safe_payload_hash(value: Any) -> str:
    canonical = json.dumps(redact_for_hash(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BudgetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deadline_at: datetime | None = None
    total_deadline_seconds: int | None = Field(default=None, ge=1)
    per_attempt_timeout_seconds: int | None = Field(default=None, ge=1)
    token_budget: int | None = Field(default=None, ge=0)
    cost_budget_usd: float | None = Field(default=None, ge=0)

    @field_validator("deadline_at")
    @classmethod
    def deadline_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return require_aware_datetime(value) if value else value


class SideEffectProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_type: StepType
    automatic_retry_allowed: bool = False
    idempotency_required: bool = False
    rollback_supported: bool = False
    compensating_action: str | None = None
    human_approval_required: bool = False
    irreversible: bool = False
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=240)
    checkpoint_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_safe_side_effect_metadata(self) -> "SideEffectProfile":
        if self.step_type == StepType.EXTERNAL_ACTION:
            self.automatic_retry_allowed = False
            self.human_approval_required = True
        if self.irreversible:
            self.automatic_retry_allowed = False
            self.rollback_supported = False
        if self.step_type == StepType.DATABASE_WRITE:
            self.idempotency_required = True
            if not self.idempotency_key:
                self.automatic_retry_allowed = False
        if self.rollback_supported and not (self.checkpoint_reference or self.compensating_action):
            self.rollback_supported = False
        return self


def derive_side_effect_profile(step_type: StepType, metadata: dict[str, Any] | None = None) -> SideEffectProfile:
    metadata = metadata or {}
    idempotency_key = metadata.get("idempotency_key")
    checkpoint = metadata.get("checkpoint_reference")
    compensating_action = metadata.get("compensating_action")
    if step_type in {StepType.MODEL_GENERATION, StepType.READ_ONLY_API, StepType.DATABASE_READ}:
        return SideEffectProfile(
            step_type=step_type,
            automatic_retry_allowed=True,
            idempotency_required=False,
            rollback_supported=False,
            idempotency_key=idempotency_key,
        )
    if step_type == StepType.DATABASE_WRITE:
        return SideEffectProfile(
            step_type=step_type,
            automatic_retry_allowed=bool(idempotency_key),
            idempotency_required=True,
            rollback_supported=bool(checkpoint or compensating_action),
            idempotency_key=idempotency_key,
            checkpoint_reference=checkpoint,
            compensating_action=compensating_action,
        )
    if step_type == StepType.INTERNAL_STATE_CHANGE:
        return SideEffectProfile(
            step_type=step_type,
            automatic_retry_allowed=bool(idempotency_key),
            idempotency_required=True,
            rollback_supported=bool(checkpoint or compensating_action),
            idempotency_key=idempotency_key,
            checkpoint_reference=checkpoint,
            compensating_action=compensating_action,
        )
    return SideEffectProfile(
        step_type=step_type,
        automatic_retry_allowed=False,
        human_approval_required=True,
        irreversible=bool(metadata.get("irreversible", True)),
        idempotency_key=idempotency_key,
    )


class StepEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    contract_version: str = Field(CONTRACT_VERSION, min_length=1, max_length=40)
    organization_id: str
    project_id: str
    environment_id: str | None = Field(default=None, max_length=160)
    environment: str = Field("development", max_length=80)
    workflow_id: str
    trace_id: str
    step_id: str
    parent_step_id: str | None = Field(default=None, max_length=160)
    agent_id: str | None = Field(default=None, max_length=160)
    component_name: str | None = Field(default=None, max_length=160)
    step_type: StepType = StepType.MODEL_GENERATION
    attempt_number: int = Field(1, ge=1)
    input: Any = Field(default_factory=dict)
    output: Any = Field(default_factory=dict)
    expected_contract: dict[str, Any] | None = None
    tool_actions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    workflow_version: str = Field("unversioned", min_length=1, max_length=120)
    created_at: datetime = Field(default_factory=now_utc)
    budget: BudgetInfo | None = None
    side_effect: SideEffectProfile | None = None

    @field_validator("organization_id", "project_id", "environment", "workflow_id", "trace_id", "step_id")
    @classmethod
    def tenant_identifiers_are_safe(cls, value: str, info) -> str:
        return validate_identifier(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_aware(cls, value: datetime) -> datetime:
        return require_aware_datetime(value)

    @model_validator(mode="after")
    def normalize_environment_and_side_effect(self) -> "StepEnvelope":
        if not self.environment_id:
            self.environment_id = self.environment
        if not self.agent_id and not self.component_name:
            raise ValueError("agent_id or component_name is required")
        if self.side_effect is None:
            self.side_effect = derive_side_effect_profile(self.step_type, self.metadata)
        return self

    @property
    def tenant_key(self) -> tuple[str, str, str]:
        return (self.organization_id, self.project_id, self.environment_id or self.environment)

    @property
    def input_hash(self) -> str:
        return safe_payload_hash(self.input)

    @property
    def output_hash(self) -> str:
        return safe_payload_hash(self.output)


class ValidationErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: list[str | int] = Field(default_factory=list)
    code: str
    message: str
    severity: Severity = Severity.ERROR


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    validator_version: str = VALIDATOR_VERSION
    valid: bool
    errors: list[ValidationErrorDetail] = Field(default_factory=list)
    severity: Severity = Severity.INFO
    checked_at: datetime = Field(default_factory=now_utc)

    @field_validator("checked_at")
    @classmethod
    def checked_at_must_be_aware(cls, value: datetime) -> datetime:
        return require_aware_datetime(value)


class RecoveryAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str = Field(default_factory=lambda: f"recovery_{uuid4().hex}")
    organization_id: str
    project_id: str
    environment: str
    workflow_id: str
    trace_id: str
    step_id: str
    attempt_number: int = Field(..., ge=1)
    policy_version: str
    action: RecoveryAction
    status: RecoveryStatus = RecoveryStatus.PENDING
    validation_errors: list[ValidationErrorDetail] = Field(default_factory=list)
    expected_contract: dict[str, Any] | None = None
    idempotency_key: str | None = None
    started_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None
    output_hash: str | None = None
    outcome: str | None = None


class ReliabilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(default_factory=lambda: f"decision_{uuid4().hex}")
    organization_id: str
    project_id: str
    environment: str
    workflow_id: str
    trace_id: str
    step_id: str
    attempt_number: int = Field(..., ge=1)
    policy_version: str
    validator_version: str = VALIDATOR_VERSION
    reliability_engine_version: str = ENGINE_VERSION
    workflow_version: str
    contract_version: str
    input_hash: str
    output_hash: str
    validator_results: list[ValidationResult] = Field(default_factory=list)
    selected_decision: DecisionAction
    reasons: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    selected_recovery_action: RecoveryAction = RecoveryAction.NONE
    recovery_outcome: str | None = None
    release_allowed: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    decided_at: datetime = Field(default_factory=now_utc)

    @field_validator("created_at", "decided_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime) -> datetime:
        return require_aware_datetime(value)


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_event_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    event_type: Literal["reliability.decision"] = "reliability.decision"
    organization_id: str
    project_id: str
    environment: str
    workflow_id: str
    trace_id: str
    step_id: str
    attempt_number: int = Field(..., ge=1)
    policy_version: str
    validator_version: str
    reliability_engine_version: str
    workflow_version: str
    contract_version: str
    input_hash: str
    output_hash: str
    validator_results: list[ValidationResult]
    selected_decision: DecisionAction
    reasons: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    selected_recovery_action: RecoveryAction = RecoveryAction.NONE
    recovery_outcome: str | None = None
    recovery_attempts: list[RecoveryAttempt] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_aware(cls, value: datetime) -> datetime:
        return require_aware_datetime(value)
