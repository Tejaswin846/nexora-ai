from __future__ import annotations

from ..contracts.models import (
    DecisionAction,
    RecoveryAction,
    ReliabilityDecision,
    StepEnvelope,
    StepType,
    ValidationResult,
)
from ..policies.recovery_policy import RecoveryPolicy


class DecisionEngine:
    def decide(
        self,
        envelope: StepEnvelope,
        validation: ValidationResult,
        policy: RecoveryPolicy,
        *,
        recovery_attempts_used: int = 0,
    ) -> ReliabilityDecision:
        if validation.valid:
            return self._decision(
                envelope,
                validation,
                policy,
                action=DecisionAction.ALLOW,
                recovery_action=RecoveryAction.NONE,
                release_allowed=True,
                reasons=["Output satisfied the expected contract."],
                reason_codes=["contract.valid"],
            )

        profile = envelope.side_effect
        if profile and profile.step_type == StepType.EXTERNAL_ACTION:
            return self._decision(
                envelope,
                validation,
                policy,
                action=DecisionAction.ESCALATE,
                recovery_action=RecoveryAction.HUMAN_REVIEW,
                release_allowed=False,
                reasons=["External side effects require human review before retry."],
                reason_codes=["side_effect.external_action.no_blind_retry"],
            )

        if (
            profile
            and profile.step_type
            in {StepType.DATABASE_WRITE, StepType.INTERNAL_STATE_CHANGE}
            and not profile.idempotency_key
        ):
            return self._decision(
                envelope,
                validation,
                policy,
                action=DecisionAction.BLOCK,
                recovery_action=RecoveryAction.NONE,
                release_allowed=False,
                reasons=[
                    "Retryable writes require an idempotency key or verified transaction strategy."
                ],
                reason_codes=["side_effect.idempotency_required"],
            )

        if profile and profile.irreversible:
            return self._decision(
                envelope,
                validation,
                policy,
                action=DecisionAction.ESCALATE,
                recovery_action=RecoveryAction.HUMAN_REVIEW,
                release_allowed=False,
                reasons=[
                    "Irreversible actions cannot be automatically retried or rolled back."
                ],
                reason_codes=["side_effect.irreversible"],
            )

        failure_classes = {error.code for error in validation.errors} | {
            "schema_validation"
        }
        retryable = (
            bool(failure_classes & policy.retryable_failure_classes)
            or "schema_validation" in policy.retryable_failure_classes
        )
        recovery_allowed = (
            retryable
            and RecoveryAction.CORRECT_OUTPUT in policy.allowed_recovery_actions
            and policy.attempts_remaining_for_step(recovery_attempts_used)
            and (profile is None or profile.automatic_retry_allowed)
        )
        if recovery_allowed:
            return self._decision(
                envelope,
                validation,
                policy,
                action=DecisionAction.CORRECT_AND_RETRY,
                recovery_action=RecoveryAction.CORRECT_OUTPUT,
                release_allowed=False,
                reasons=[
                    "Structured output failed validation and corrective retry is within policy."
                ],
                reason_codes=["contract.invalid.corrective_retry_allowed"],
            )

        return self._decision(
            envelope,
            validation,
            policy,
            action=policy.final_action_after_exhaustion,
            recovery_action=RecoveryAction.NONE,
            release_allowed=False,
            reasons=["Validation failed and no safe recovery attempt remains."],
            reason_codes=["recovery.exhausted"],
        )

    @staticmethod
    def _decision(
        envelope: StepEnvelope,
        validation: ValidationResult,
        policy: RecoveryPolicy,
        *,
        action: DecisionAction,
        recovery_action: RecoveryAction,
        release_allowed: bool,
        reasons: list[str],
        reason_codes: list[str],
    ) -> ReliabilityDecision:
        return ReliabilityDecision(
            organization_id=envelope.organization_id,
            project_id=envelope.project_id,
            environment=envelope.environment_id or envelope.environment,
            workflow_id=envelope.workflow_id,
            trace_id=envelope.trace_id,
            step_id=envelope.step_id,
            attempt_number=envelope.attempt_number,
            policy_version=policy.policy_version,
            validator_version=validation.validator_version,
            workflow_version=envelope.workflow_version,
            contract_version=validation.contract_version,
            input_hash=envelope.input_hash,
            output_hash=envelope.output_hash,
            validator_results=[validation],
            selected_decision=action,
            reasons=reasons,
            reason_codes=reason_codes,
            selected_recovery_action=recovery_action,
            release_allowed=release_allowed,
        )
