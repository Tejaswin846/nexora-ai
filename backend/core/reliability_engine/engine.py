from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..audit.audit_writer import AuditWriter
from ..contracts.models import DecisionAction, RecoveryAction, RecoveryAttempt, ReliabilityDecision, StepEnvelope, ValidationResult
from ..decisions.decision_engine import DecisionEngine
from ..events.background import SafeBackgroundEventPublisher
from ..policies.recovery_policy import RecoveryPolicy
from ..recovery.recovery_executor import RecoveryExecutor
from ..validation.contract_validator import ContractValidator
from ..validation.revalidator import Revalidator


@dataclass(frozen=True)
class ReliabilityEngineResult:
    release_allowed: bool
    released_output: Any
    initial_validation: ValidationResult
    final_validation: ValidationResult
    decision: ReliabilityDecision
    recovery_attempts: list[RecoveryAttempt]
    background_errors: list[str]
    audit_event_id: str

    def to_api_payload(self) -> dict[str, Any]:
        return {
            "release_allowed": self.release_allowed,
            "released_output": self.released_output if self.release_allowed else None,
            "initial_validation": self.initial_validation.model_dump(mode="json"),
            "final_validation": self.final_validation.model_dump(mode="json"),
            "decision": self.decision.model_dump(mode="json"),
            "recovery_attempts": [attempt.model_dump(mode="json") for attempt in self.recovery_attempts],
            "background_errors": self.background_errors,
            "audit_event_id": self.audit_event_id,
        }


class ReliabilityEngine:
    def __init__(
        self,
        *,
        validator: ContractValidator,
        decision_engine: DecisionEngine,
        recovery_executor: RecoveryExecutor,
        audit_writer: AuditWriter,
        revalidator: Revalidator | None = None,
        background_publisher: SafeBackgroundEventPublisher | None = None,
        policy: RecoveryPolicy | None = None,
    ) -> None:
        self.validator = validator
        self.decision_engine = decision_engine
        self.recovery_executor = recovery_executor
        self.revalidator = revalidator or Revalidator(validator)
        self.audit_writer = audit_writer
        self.background_publisher = background_publisher or SafeBackgroundEventPublisher()
        self.policy = policy or RecoveryPolicy()

    def evaluate(self, envelope: StepEnvelope, policy: RecoveryPolicy | None = None) -> ReliabilityEngineResult:
        policy = policy or self.policy
        background_failure_start = len(self.background_publisher.failures)
        initial_validation = self.validator.validate(envelope)
        decision_history: list[ReliabilityDecision] = []
        recovery_attempts: list[RecoveryAttempt] = []
        validation_results: list[ValidationResult] = [initial_validation]

        decision = self.decision_engine.decide(envelope, initial_validation, policy, recovery_attempts_used=0)
        decision_history.append(decision)
        final_validation = initial_validation
        released_output = envelope.output if decision.release_allowed else None

        while decision.selected_decision == DecisionAction.CORRECT_AND_RETRY and len(recovery_attempts) < policy.maximum_attempts_per_step:
            attempt_number = len(recovery_attempts) + 1
            attempt, candidate_output = self.recovery_executor.execute(
                envelope,
                final_validation,
                policy,
                attempt_number=attempt_number,
            )
            recovery_attempts.append(attempt)
            recovered_envelope = envelope.model_copy(update={"output": candidate_output, "attempt_number": envelope.attempt_number + attempt_number})
            final_validation = self.revalidator.revalidate(envelope, candidate_output, recovered_envelope.attempt_number)
            validation_results.append(final_validation)
            if final_validation.valid:
                decision = self.decision_engine.decide(recovered_envelope, final_validation, policy, recovery_attempts_used=len(recovery_attempts))
                decision.recovery_outcome = attempt.outcome
                decision.selected_recovery_action = RecoveryAction.NONE
                decision_history.append(decision)
                released_output = candidate_output
                break
            decision = self.decision_engine.decide(recovered_envelope, final_validation, policy, recovery_attempts_used=len(recovery_attempts))
            decision.recovery_outcome = attempt.outcome
            decision_history.append(decision)
            released_output = None

        self.background_publisher.publish(
            "reliability.validation.completed",
            {
                "organization_id": envelope.organization_id,
                "project_id": envelope.project_id,
                "environment": envelope.environment_id or envelope.environment,
                "workflow_id": envelope.workflow_id,
                "trace_id": envelope.trace_id,
                "step_id": envelope.step_id,
                "decision": decision.selected_decision,
            },
        )
        background_errors = list(self.background_publisher.failures[background_failure_start:])
        audit_event = self.audit_writer.write(
            envelope=envelope,
            final_decision=decision,
            validation_results=validation_results,
            recovery_attempts=recovery_attempts,
            decision_history=decision_history,
            background_errors=background_errors,
        )
        return ReliabilityEngineResult(
            release_allowed=decision.release_allowed,
            released_output=released_output if decision.release_allowed else None,
            initial_validation=initial_validation,
            final_validation=final_validation,
            decision=decision,
            recovery_attempts=recovery_attempts,
            background_errors=background_errors,
            audit_event_id=audit_event.audit_event_id,
        )
