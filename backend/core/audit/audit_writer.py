from __future__ import annotations

from typing import Protocol

from ..contracts.models import (
    AuditEvent,
    RecoveryAttempt,
    ReliabilityDecision,
    StepEnvelope,
    ValidationResult,
)


class AuditRepository(Protocol):
    def record_decision(self, event: AuditEvent) -> None: ...


class AuditWriter:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def write(
        self,
        *,
        envelope: StepEnvelope,
        final_decision: ReliabilityDecision,
        validation_results: list[ValidationResult],
        recovery_attempts: list[RecoveryAttempt],
        decision_history: list[ReliabilityDecision],
        background_errors: list[str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            organization_id=envelope.organization_id,
            project_id=envelope.project_id,
            environment=envelope.environment_id or envelope.environment,
            workflow_id=envelope.workflow_id,
            trace_id=envelope.trace_id,
            step_id=envelope.step_id,
            attempt_number=final_decision.attempt_number,
            policy_version=final_decision.policy_version,
            validator_version=final_decision.validator_version,
            reliability_engine_version=final_decision.reliability_engine_version,
            workflow_version=final_decision.workflow_version,
            contract_version=final_decision.contract_version,
            input_hash=final_decision.input_hash,
            output_hash=final_decision.output_hash,
            validator_results=validation_results,
            selected_decision=final_decision.selected_decision,
            reasons=final_decision.reasons,
            reason_codes=final_decision.reason_codes,
            selected_recovery_action=final_decision.selected_recovery_action,
            recovery_outcome=final_decision.recovery_outcome,
            recovery_attempts=recovery_attempts,
            metadata={
                "decision_history": [
                    decision.model_dump(mode="json") for decision in decision_history
                ],
                "background_errors": background_errors or [],
            },
        )
        self.repository.record_decision(event)
        return event
