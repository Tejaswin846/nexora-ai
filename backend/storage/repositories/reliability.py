from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from pydantic import BaseModel

try:
    from core.contracts.models import AuditEvent, ReliabilityDecision
except Exception:
    from ...core.contracts.models import AuditEvent, ReliabilityDecision


@dataclass(frozen=True)
class TenantScope:
    organization_id: str
    project_id: str
    environment: str

    def matches(self, organization_id: str, project_id: str, environment: str) -> bool:
        return (
            self.organization_id == organization_id
            and self.project_id == project_id
            and self.environment == environment
        )


class ReliabilityRepository(Protocol):
    def record_decision(self, event: AuditEvent) -> None: ...
    def list_audit_events(self, scope: TenantScope, *, trace_id: str | None = None) -> list[AuditEvent]: ...
    def get_decision(self, scope: TenantScope, decision_id: str) -> ReliabilityDecision | None: ...


class InMemoryReliabilityRepository:
    def __init__(self) -> None:
        self.audit_events: list[AuditEvent] = []
        self.decisions: dict[str, ReliabilityDecision] = {}

    def record_decision(self, event: AuditEvent) -> None:
        self.audit_events.append(event)
        for raw_decision in event.metadata.get("decision_history", []):
            decision = ReliabilityDecision.model_validate(raw_decision)
            self.decisions[decision.decision_id] = decision

    def list_audit_events(self, scope: TenantScope, *, trace_id: str | None = None) -> list[AuditEvent]:
        events = [
            event
            for event in self.audit_events
            if scope.matches(event.organization_id, event.project_id, event.environment)
        ]
        if trace_id:
            events = [event for event in events if event.trace_id == trace_id]
        return list(events)

    def get_decision(self, scope: TenantScope, decision_id: str) -> ReliabilityDecision | None:
        decision = self.decisions.get(decision_id)
        if decision is None:
            return None
        if not scope.matches(decision.organization_id, decision.project_id, decision.environment):
            return None
        return decision


class SqlReliabilityRepository:
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self.session_factory = session_factory

    def record_decision(self, event: AuditEvent) -> None:
        session = self.session_factory()
        try:
            self._insert_audit_event(session, event)
            for raw_decision in event.metadata.get("decision_history", []):
                self._insert_decision(session, ReliabilityDecision.model_validate(raw_decision), event.audit_event_id)
            session.commit()
        finally:
            session.close()

    def list_audit_events(self, scope: TenantScope, *, trace_id: str | None = None) -> list[AuditEvent]:
        session = self.session_factory()
        try:
            if session.backend == "sqlite":
                query = (
                    "SELECT payload_json FROM software_audit_events "
                    "WHERE organization_id = ? AND project_id = ? AND environment = ?"
                )
                params: tuple[Any, ...] = (scope.organization_id, scope.project_id, scope.environment)
                if trace_id:
                    query += " AND trace_id = ?"
                    params += (trace_id,)
                rows = session.execute(query, params).fetchall()
            else:
                query = (
                    "SELECT payload_json FROM software_audit_events "
                    "WHERE organization_id = :organization_id AND project_id = :project_id AND environment = :environment"
                )
                params = {
                    "organization_id": scope.organization_id,
                    "project_id": scope.project_id,
                    "environment": scope.environment,
                }
                if trace_id:
                    query += " AND trace_id = :trace_id"
                    params["trace_id"] = trace_id
                rows = session.execute(query, params).fetchall()
            return [AuditEvent.model_validate_json(row[0] if not hasattr(row, "_mapping") else row._mapping["payload_json"]) for row in rows]
        finally:
            session.close()

    def get_decision(self, scope: TenantScope, decision_id: str) -> ReliabilityDecision | None:
        session = self.session_factory()
        try:
            if session.backend == "sqlite":
                row = session.execute(
                    """
                    SELECT payload_json FROM software_reliability_decisions
                    WHERE decision_id = ? AND organization_id = ? AND project_id = ? AND environment = ?
                    """,
                    (decision_id, scope.organization_id, scope.project_id, scope.environment),
                ).fetchone()
            else:
                row = session.execute(
                    """
                    SELECT payload_json FROM software_reliability_decisions
                    WHERE decision_id = :decision_id AND organization_id = :organization_id
                      AND project_id = :project_id AND environment = :environment
                    """,
                    {
                        "decision_id": decision_id,
                        "organization_id": scope.organization_id,
                        "project_id": scope.project_id,
                        "environment": scope.environment,
                    },
                ).fetchone()
            if row is None:
                return None
            payload = row[0] if not hasattr(row, "_mapping") else row._mapping["payload_json"]
            return ReliabilityDecision.model_validate_json(payload)
        finally:
            session.close()

    @staticmethod
    def _json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def _insert_audit_event(self, session: Any, event: AuditEvent) -> None:
        values = {
            "audit_event_id": event.audit_event_id,
            "organization_id": event.organization_id,
            "project_id": event.project_id,
            "environment": event.environment,
            "workflow_id": event.workflow_id,
            "trace_id": event.trace_id,
            "step_id": event.step_id,
            "attempt_number": event.attempt_number,
            "selected_decision": event.selected_decision.value,
            "policy_version": event.policy_version,
            "created_at": event.created_at.isoformat(),
            "payload_json": self._json(event),
        }
        if session.backend == "sqlite":
            session.execute(
                """
                INSERT INTO software_audit_events (
                    audit_event_id, organization_id, project_id, environment, workflow_id, trace_id,
                    step_id, attempt_number, selected_decision, policy_version, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(values.values()),
            )
            return
        session.execute(
            """
            INSERT INTO software_audit_events (
                audit_event_id, organization_id, project_id, environment, workflow_id, trace_id,
                step_id, attempt_number, selected_decision, policy_version, created_at, payload_json
            )
            VALUES (
                :audit_event_id, :organization_id, :project_id, :environment, :workflow_id, :trace_id,
                :step_id, :attempt_number, :selected_decision, :policy_version, :created_at, CAST(:payload_json AS jsonb)
            )
            """,
            values,
        )

    def _insert_decision(self, session: Any, decision: ReliabilityDecision, audit_event_id: str) -> None:
        values = {
            "decision_id": decision.decision_id,
            "audit_event_id": audit_event_id,
            "organization_id": decision.organization_id,
            "project_id": decision.project_id,
            "environment": decision.environment,
            "workflow_id": decision.workflow_id,
            "trace_id": decision.trace_id,
            "step_id": decision.step_id,
            "attempt_number": decision.attempt_number,
            "selected_decision": decision.selected_decision.value,
            "policy_version": decision.policy_version,
            "validator_version": decision.validator_version,
            "reliability_engine_version": decision.reliability_engine_version,
            "workflow_version": decision.workflow_version,
            "contract_version": decision.contract_version,
            "input_hash": decision.input_hash,
            "output_hash": decision.output_hash,
            "created_at": decision.created_at.isoformat(),
            "payload_json": self._json(decision),
        }
        if session.backend == "sqlite":
            session.execute(
                """
                INSERT OR REPLACE INTO software_reliability_decisions (
                    decision_id, audit_event_id, organization_id, project_id, environment, workflow_id, trace_id,
                    step_id, attempt_number, selected_decision, policy_version, validator_version,
                    reliability_engine_version, workflow_version, contract_version, input_hash, output_hash,
                    created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(values.values()),
            )
            return
        session.execute(
            """
            INSERT INTO software_reliability_decisions (
                decision_id, audit_event_id, organization_id, project_id, environment, workflow_id, trace_id,
                step_id, attempt_number, selected_decision, policy_version, validator_version,
                reliability_engine_version, workflow_version, contract_version, input_hash, output_hash,
                created_at, payload_json
            )
            VALUES (
                :decision_id, :audit_event_id, :organization_id, :project_id, :environment, :workflow_id, :trace_id,
                :step_id, :attempt_number, :selected_decision, :policy_version, :validator_version,
                :reliability_engine_version, :workflow_version, :contract_version, :input_hash, :output_hash,
                :created_at, CAST(:payload_json AS jsonb)
            )
            ON CONFLICT (decision_id) DO UPDATE SET payload_json = EXCLUDED.payload_json
            """,
            values,
        )
