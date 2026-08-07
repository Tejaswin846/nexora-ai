from __future__ import annotations

from functools import lru_cache
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

try:
    from adapters.legacy.reliability import legacy_step_payload_to_envelope
    from core.audit.audit_writer import AuditWriter
    from core.contracts.models import StepEnvelope
    from core.decisions.decision_engine import DecisionEngine
    from core.events.background import SafeBackgroundEventPublisher
    from core.policies.recovery_policy import RecoveryPolicy
    from core.recovery.recovery_executor import DeterministicJsonSchemaRecoveryProvider, RecoveryExecutor
    from core.reliability_engine.engine import ReliabilityEngine
    from core.validation.contract_validator import ContractValidator
    from core.validation.revalidator import Revalidator
    from config import get_settings
    from database import init_database, open_database_session
    from storage.repositories.reliability import InMemoryReliabilityRepository, SqlReliabilityRepository
except Exception:
    from ..adapters.legacy.reliability import legacy_step_payload_to_envelope
    from ..core.audit.audit_writer import AuditWriter
    from ..core.contracts.models import StepEnvelope
    from ..core.decisions.decision_engine import DecisionEngine
    from ..core.events.background import SafeBackgroundEventPublisher
    from ..core.policies.recovery_policy import RecoveryPolicy
    from ..core.recovery.recovery_executor import DeterministicJsonSchemaRecoveryProvider, RecoveryExecutor
    from ..core.reliability_engine.engine import ReliabilityEngine
    from ..core.validation.contract_validator import ContractValidator
    from ..core.validation.revalidator import Revalidator
    from ..config import get_settings
    from ..database import init_database, open_database_session
    from ..storage.repositories.reliability import InMemoryReliabilityRepository, SqlReliabilityRepository


router = APIRouter(prefix="/api/reliability", tags=["reliability"])


def _session_factory():
    return open_database_session()


@lru_cache(maxsize=1)
def get_reliability_engine() -> ReliabilityEngine:
    settings = get_settings()
    try:
        init_database()
        repository = SqlReliabilityRepository(_session_factory)
    except Exception:
        if settings.is_production_like:
            raise
        repository = InMemoryReliabilityRepository()
    policy = RecoveryPolicy(
        policy_version=os.getenv("NEXORA_RECOVERY_POLICY_VERSION", "recovery-policy-v1").strip() or "recovery-policy-v1",
        maximum_attempts_per_step=int(os.getenv("NEXORA_RECOVERY_MAX_ATTEMPTS_PER_STEP", "1")),
        maximum_attempts_per_workflow=int(os.getenv("NEXORA_RECOVERY_MAX_ATTEMPTS_PER_WORKFLOW", "5")),
    )
    validator = ContractValidator()
    return ReliabilityEngine(
        validator=validator,
        decision_engine=DecisionEngine(),
        recovery_executor=RecoveryExecutor(DeterministicJsonSchemaRecoveryProvider()),
        revalidator=Revalidator(validator),
        audit_writer=AuditWriter(repository),
        background_publisher=SafeBackgroundEventPublisher(),
        policy=policy,
    )


@router.post("/steps/evaluate")
def evaluate_step(
    envelope: StepEnvelope,
    engine: ReliabilityEngine = Depends(get_reliability_engine),
) -> dict[str, Any]:
    try:
        return engine.evaluate(envelope).to_api_payload()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Reliability Engine is unavailable.") from error


@router.post("/legacy/evaluate")
def evaluate_legacy_step(
    payload: dict[str, Any],
    engine: ReliabilityEngine = Depends(get_reliability_engine),
    x_organization_id: str | None = Header(default=None),
    x_project_id: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_organization_id and "organization_id" not in payload:
        payload["organization_id"] = x_organization_id
    if x_project_id and "project_id" not in payload:
        payload["project_id"] = x_project_id
    try:
        envelope = legacy_step_payload_to_envelope(payload)
        return engine.evaluate(envelope).to_api_payload()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Reliability Engine is unavailable.") from error
