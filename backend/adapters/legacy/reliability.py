from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from core.contracts.models import StepEnvelope, StepType
except Exception:
    from ...core.contracts.models import StepEnvelope, StepType


def legacy_step_payload_to_envelope(payload: dict[str, Any]) -> StepEnvelope:
    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("legacy_payload_shape", True)
    if "recovery_output" in payload and "recovery_output" not in metadata:
        metadata["recovery_output"] = payload["recovery_output"]

    step_type = payload.get("step_type") or payload.get("type") or StepType.MODEL_GENERATION
    output = payload.get("output", payload.get("result", {}))
    return StepEnvelope(
        contract_version=str(payload.get("contract_version") or "1.0"),
        organization_id=str(payload.get("organization_id") or payload.get("tenant_id") or "default-org"),
        project_id=str(payload.get("project_id") or "default-project"),
        environment_id=payload.get("environment_id"),
        environment=str(payload.get("environment") or "development"),
        workflow_id=str(payload.get("workflow_id") or payload.get("run_id") or "legacy-workflow"),
        trace_id=str(payload.get("trace_id") or payload.get("request_id") or "legacy-trace"),
        step_id=str(payload.get("step_id") or payload.get("stage_name") or "legacy-step"),
        parent_step_id=payload.get("parent_step_id"),
        agent_id=payload.get("agent_id"),
        component_name=str(payload.get("component_name") or payload.get("agent") or "legacy-adapter"),
        step_type=StepType(step_type),
        attempt_number=int(payload.get("attempt_number") or 1),
        input=payload.get("input", {}),
        output=output,
        expected_contract=payload.get("expected_contract"),
        tool_actions=list(payload.get("tool_actions") or []),
        metadata=metadata,
        workflow_version=str(payload.get("workflow_version") or "legacy-unversioned"),
        created_at=payload.get("created_at") or datetime.now(timezone.utc),
        budget=payload.get("budget"),
        side_effect=payload.get("side_effect"),
    )
