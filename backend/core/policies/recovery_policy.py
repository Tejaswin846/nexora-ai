from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..contracts.models import DecisionAction, RecoveryAction


class BackoffConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_seconds: float = Field(0.1, ge=0)
    multiplier: float = Field(2.0, ge=1)
    max_seconds: float = Field(5.0, ge=0)


class RecoveryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str = Field("recovery-policy-v1", min_length=1, max_length=120)
    maximum_attempts_per_step: int = Field(1, ge=0, le=20)
    maximum_attempts_per_workflow: int = Field(5, ge=0, le=100)
    total_deadline_seconds: int | None = Field(default=60, ge=1)
    per_attempt_timeout_seconds: int | None = Field(default=10, ge=1)
    token_budget: int | None = Field(default=None, ge=0)
    cost_budget_usd: float | None = Field(default=None, ge=0)
    allowed_recovery_actions: set[RecoveryAction] = Field(
        default_factory=lambda: {RecoveryAction.CORRECT_OUTPUT}
    )
    retryable_failure_classes: set[str] = Field(
        default_factory=lambda: {"schema_validation"}
    )
    backoff: BackoffConfig = Field(default_factory=BackoffConfig)
    jitter_seconds: float = Field(0.0, ge=0)
    fallback_permission: bool = False
    rollback_permission: bool = False
    human_approval_required: bool = False
    final_action_after_exhaustion: DecisionAction = DecisionAction.ESCALATE

    @model_validator(mode="after")
    def ensure_final_action_is_terminal(self) -> "RecoveryPolicy":
        if self.final_action_after_exhaustion not in {
            DecisionAction.ESCALATE,
            DecisionAction.TERMINATE,
            DecisionAction.BLOCK,
        }:
            raise ValueError(
                "final_action_after_exhaustion must be ESCALATE, TERMINATE, or BLOCK"
            )
        if self.maximum_attempts_per_step == 0:
            self.allowed_recovery_actions = set()
        if not self.fallback_permission:
            self.allowed_recovery_actions.discard(RecoveryAction.FALLBACK)
        if not self.rollback_permission:
            self.allowed_recovery_actions.discard(RecoveryAction.ROLLBACK)
        return self

    @property
    def total_deadline(self) -> timedelta | None:
        return (
            timedelta(seconds=self.total_deadline_seconds)
            if self.total_deadline_seconds
            else None
        )

    def attempts_remaining_for_step(self, attempted: int) -> bool:
        return attempted < self.maximum_attempts_per_step
