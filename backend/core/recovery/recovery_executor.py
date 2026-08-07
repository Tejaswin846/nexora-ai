from __future__ import annotations

from typing import Any, Protocol

from ..contracts.models import (
    RecoveryAction,
    RecoveryAttempt,
    RecoveryStatus,
    StepEnvelope,
    ValidationResult,
    now_utc,
    safe_payload_hash,
)
from ..policies.recovery_policy import RecoveryPolicy


class RecoveryProvider(Protocol):
    def correct_output(self, envelope: StepEnvelope, validation: ValidationResult, attempt_number: int) -> Any: ...


class IdempotencyStore(Protocol):
    def reserve(self, key: str, fingerprint: str) -> bool: ...
    def complete(self, key: str, fingerprint: str, outcome: str) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def reserve(self, key: str, fingerprint: str) -> bool:
        if key in self._records:
            return False
        self._records[key] = (fingerprint, "reserved")
        return True

    def complete(self, key: str, fingerprint: str, outcome: str) -> None:
        self._records[key] = (fingerprint, outcome)


class DeterministicJsonSchemaRecoveryProvider:
    def correct_output(self, envelope: StepEnvelope, validation: ValidationResult, attempt_number: int) -> Any:
        if "recovery_output" in envelope.metadata:
            return envelope.metadata["recovery_output"]
        schema = (envelope.expected_contract or {}).get("schema") or envelope.expected_contract or {}
        if not isinstance(schema, dict) or not isinstance(envelope.output, dict):
            return envelope.output
        corrected = dict(envelope.output)
        properties = schema.get("properties") or {}
        for key, property_schema in properties.items():
            if key in corrected and isinstance(property_schema, dict):
                corrected[key] = self._coerce_value(corrected[key], property_schema)
        for required in schema.get("required", []):
            if required in corrected:
                continue
            property_schema = properties.get(required) if isinstance(properties.get(required), dict) else {}
            if "default" in property_schema:
                corrected[required] = property_schema["default"]
            elif "examples" in property_schema and property_schema["examples"]:
                corrected[required] = property_schema["examples"][0]
            elif property_schema.get("type") == "string":
                corrected[required] = ""
            elif property_schema.get("type") in {"number", "integer"}:
                corrected[required] = 0
            elif property_schema.get("type") == "boolean":
                corrected[required] = False
            elif property_schema.get("type") == "array":
                corrected[required] = []
            else:
                corrected[required] = {}
        return corrected

    @staticmethod
    def _coerce_value(value: Any, schema: dict[str, Any]) -> Any:
        expected_type = schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            return str(value)
        if expected_type == "number" and not isinstance(value, (int, float)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if expected_type == "integer" and not isinstance(value, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if expected_type == "boolean" and not isinstance(value, bool):
            if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
                return value.strip().lower() == "true"
        return value


class RecoveryExecutor:
    def __init__(
        self,
        provider: RecoveryProvider | None = None,
        idempotency_store: IdempotencyStore | None = None,
    ) -> None:
        self.provider = provider or DeterministicJsonSchemaRecoveryProvider()
        self.idempotency_store = idempotency_store or InMemoryIdempotencyStore()

    def execute(
        self,
        envelope: StepEnvelope,
        validation: ValidationResult,
        policy: RecoveryPolicy,
        *,
        attempt_number: int,
    ) -> tuple[RecoveryAttempt, Any]:
        action = RecoveryAction.CORRECT_OUTPUT
        attempt = RecoveryAttempt(
            organization_id=envelope.organization_id,
            project_id=envelope.project_id,
            environment=envelope.environment_id or envelope.environment,
            workflow_id=envelope.workflow_id,
            trace_id=envelope.trace_id,
            step_id=envelope.step_id,
            attempt_number=attempt_number,
            policy_version=policy.policy_version,
            action=action,
            validation_errors=validation.errors,
            expected_contract=envelope.expected_contract,
            idempotency_key=envelope.side_effect.idempotency_key if envelope.side_effect else None,
        )
        if action not in policy.allowed_recovery_actions:
            attempt.status = RecoveryStatus.SKIPPED
            attempt.completed_at = now_utc()
            attempt.outcome = "recovery_action_not_allowed"
            return attempt, envelope.output

        idempotency_key = attempt.idempotency_key
        fingerprint = safe_payload_hash(
            {
                "organization_id": envelope.organization_id,
                "project_id": envelope.project_id,
                "environment": envelope.environment_id or envelope.environment,
                "workflow_id": envelope.workflow_id,
                "trace_id": envelope.trace_id,
                "step_id": envelope.step_id,
                "attempt_number": attempt_number,
                "validation_errors": [error.model_dump(mode="json") for error in validation.errors],
            }
        )
        if envelope.side_effect and envelope.side_effect.idempotency_required:
            if not idempotency_key:
                attempt.status = RecoveryStatus.SKIPPED
                attempt.completed_at = now_utc()
                attempt.outcome = "missing_idempotency_key"
                return attempt, envelope.output
            if not self.idempotency_store.reserve(idempotency_key, fingerprint):
                attempt.status = RecoveryStatus.DUPLICATE
                attempt.completed_at = now_utc()
                attempt.outcome = "duplicate_recovery_suppressed"
                return attempt, envelope.output

        try:
            corrected = self.provider.correct_output(envelope, validation, attempt_number)
            attempt.status = RecoveryStatus.SUCCEEDED
            attempt.output_hash = safe_payload_hash(corrected)
            attempt.outcome = "corrected_output_generated"
            if idempotency_key:
                self.idempotency_store.complete(idempotency_key, fingerprint, attempt.outcome)
            return attempt, corrected
        except Exception as error:
            attempt.status = RecoveryStatus.FAILED
            attempt.outcome = error.__class__.__name__
            if idempotency_key:
                self.idempotency_store.complete(idempotency_key, fingerprint, attempt.outcome)
            return attempt, envelope.output
        finally:
            attempt.completed_at = now_utc()
