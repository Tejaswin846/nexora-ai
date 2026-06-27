from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from .client import SoftwareClient, SoftwareClientError


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BufferedRequest:
    method_name: str
    payload: Dict[str, Any]
    error: str


class ReliabilityMonitor:
    def __init__(
        self,
        project_name: str,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        mode: str = "local",
        timeout: float = 10.0,
        raise_on_error: bool = False,
    ) -> None:
        self.project_name = project_name
        requested_mode = (mode or "local").strip().lower()
        self.mode = "cloud" if requested_mode == "cloud" or api_url else "local"
        configured_key = api_key if api_key is not None else os.getenv("SOFTWARE_API_KEY", "")
        self.client = (
            SoftwareClient(api_url=api_url or "", api_key=configured_key, timeout=timeout)
            if self.mode == "cloud"
            else None
        )
        self.raise_on_error = raise_on_error
        self.buffer: List[BufferedRequest] = []
        self.local_workflows: Dict[str, Dict[str, Any]] = {}
        self.local_events: List[Dict[str, Any]] = []

    def create_local_plan(
        self,
        goal: str,
        steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plan_steps = [step.strip() for step in (steps or []) if step and step.strip()]
        if not plan_steps:
            plan_steps = [
                "Clarify the workflow goal.",
                "List required inputs and constraints.",
                "Run the workflow in dry-run mode.",
                "Validate expected outputs and failure handling.",
                "Record the local verdict.",
            ]
        return {
            "ok": True,
            "mode": "local",
            "project_name": self.project_name,
            "goal": goal.strip(),
            "steps": plan_steps,
            "metadata": metadata or {},
            "requires_auth": False,
        }

    def validate_local_workflow(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        steps = plan.get("steps") if isinstance(plan, dict) else []
        failures: List[str] = []
        if not isinstance(steps, list) or not steps:
            failures.append("Plan must include at least one step.")
        if isinstance(plan, dict) and not str(plan.get("goal", "")).strip():
            failures.append("Plan should include a goal.")
        return {
            "ok": not failures,
            "mode": "local",
            "requires_auth": False,
            "failures": failures,
            "step_count": len(steps) if isinstance(steps, list) else 0,
        }

    def dry_run_workflow(
        self,
        workflow_name: str,
        steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        workflow_id = f"local_{uuid.uuid4().hex}"
        plan = self.create_local_plan(workflow_name, steps=steps, metadata=metadata)
        validation = self.validate_local_workflow(plan)
        self.local_workflows[workflow_id] = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": "dry_run_completed" if validation["ok"] else "dry_run_failed",
            "plan": plan,
            "validation": validation,
            "created_at": _now_iso(),
        }
        self.local_events.append({
            "workflow_id": workflow_id,
            "event_type": "dry_run",
            "created_at": _now_iso(),
            "metadata": metadata or {},
        })
        return {
            "ok": validation["ok"],
            "mode": "local",
            "requires_auth": False,
            "workflow_id": workflow_id,
            "plan": plan,
            "validation": validation,
            "side_effects": "none",
        }

    def test_sandbox_workflow(
        self,
        workflow_name: str = "sandbox workflow",
        steps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self.dry_run_workflow(
            workflow_name,
            steps=steps or [
                "Prepare dry-run inputs.",
                "Execute simulated tool calls.",
                "Verify no external side effects.",
            ],
            metadata={"sandbox": True},
        )

    def track_workflow(
        self,
        workflow_name: str,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowMonitor":
        return WorkflowMonitor(
            monitor=self,
            workflow_name=workflow_name,
            workflow_id=workflow_id or f"wf_{uuid.uuid4().hex}",
            metadata=metadata or {},
        )

    def track_stage(self, workflow_id: str, stage_name: str, **kwargs: Any) -> Dict[str, Any]:
        return self._send(
            "track_stage",
            {
                "workflow_id": workflow_id,
                "stage_name": stage_name,
                **kwargs,
            },
        )

    def log_model_call(self, workflow_id: str, model: str, success: bool, latency_ms: int, **kwargs: Any) -> Dict[str, Any]:
        return self._send(
            "log_model_call",
            {
                "workflow_id": workflow_id,
                "model": model,
                "success": success,
                "latency_ms": latency_ms,
                **kwargs,
            },
        )

    def log_tool_call(self, workflow_id: str, tool_name: str, success: bool, latency_ms: int, **kwargs: Any) -> Dict[str, Any]:
        return self._send(
            "log_tool_call",
            {
                "workflow_id": workflow_id,
                "tool_name": tool_name,
                "success": success,
                "latency_ms": latency_ms,
                **kwargs,
            },
        )

    def log_error(self, workflow_id: str, error_message: str, error_type: str = "error", **kwargs: Any) -> Dict[str, Any]:
        return self._send(
            "log_error",
            {
                "workflow_id": workflow_id,
                "error_type": error_type,
                "error_message": error_message,
                **kwargs,
            },
        )

    def predict_failure(self, workflow_id: str) -> Dict[str, Any]:
        return self._send("predict_failure", {"workflow_id": workflow_id})

    def apply_guardrail(self, workflow_id: str) -> Dict[str, Any]:
        prediction = self.predict_failure(workflow_id)
        return prediction.get("guardrail", {"action": "continue", "should_continue": True})

    def complete_workflow(
        self,
        workflow_id: str,
        success: bool,
        confidence: float,
        total_latency_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "success": success,
            "confidence": confidence,
            "metadata": metadata or {},
        }
        if total_latency_ms is not None:
            payload["total_latency_ms"] = total_latency_ms
        return self._send("complete_workflow", payload)

    def flush(self) -> Dict[str, Any]:
        if self.mode == "local":
            return {
                "sent": 0,
                "failed": 0,
                "remaining": 0,
                "mode": "local",
                "message": "Local mode does not send buffered cloud requests.",
            }
        pending = list(self.buffer)
        self.buffer.clear()
        sent = 0
        failed = 0
        for item in pending:
            try:
                if item.method_name == "predict_failure":
                    self.client.predict_failure(item.payload["workflow_id"])
                else:
                    getattr(self.client, item.method_name)(item.payload)
                sent += 1
            except SoftwareClientError as error:
                failed += 1
                self.buffer.append(BufferedRequest(item.method_name, item.payload, str(error)))
                if self.raise_on_error:
                    raise
        return {
            "sent": sent,
            "failed": failed,
            "remaining": len(self.buffer),
        }

    def _send(self, method_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "local":
            return self._send_local(method_name, payload)
        try:
            if self.client is None:
                raise SoftwareClientError("Cloud mode requires api_url.")
            return getattr(self.client, method_name)(payload) if method_name != "predict_failure" else self.client.predict_failure(payload["workflow_id"])
        except SoftwareClientError as error:
            self.buffer.append(BufferedRequest(method_name, payload, str(error)))
            if self.raise_on_error:
                raise
            return {
                "ok": False,
                "buffered": True,
                "error": str(error),
            }

    def _send_local(self, method_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = payload.get("workflow_id") or f"local_{uuid.uuid4().hex}"
        event = {
            "workflow_id": workflow_id,
            "event_type": method_name,
            "payload": dict(payload),
            "created_at": _now_iso(),
        }
        self.local_events.append(event)
        if method_name == "start_workflow":
            self.local_workflows[workflow_id] = {
                "workflow_id": workflow_id,
                "project_name": payload.get("project_name", self.project_name),
                "workflow_name": payload.get("workflow_name", "local workflow"),
                "status": "running",
                "started_at": event["created_at"],
                "events": [],
            }
            return {
                "ok": True,
                "mode": "local",
                "workflow_id": workflow_id,
                "started_at": event["created_at"],
                "requires_auth": False,
            }
        if method_name == "complete_workflow":
            workflow = self.local_workflows.setdefault(workflow_id, {"workflow_id": workflow_id})
            workflow["status"] = "completed"
            workflow["success"] = payload.get("success")
            workflow["completed_at"] = event["created_at"]
            return {
                "ok": True,
                "mode": "local",
                "workflow_id": workflow_id,
                "completed_at": event["created_at"],
                "requires_auth": False,
            }
        if method_name == "predict_failure":
            failures = sum(1 for item in self.local_events if item["workflow_id"] == workflow_id and item["payload"].get("success") is False)
            probability = min(0.95, 0.05 + failures * 0.2)
            return {
                "ok": True,
                "mode": "local",
                "workflow_id": workflow_id,
                "probability_of_failure": probability,
                "probability_of_success": round(1.0 - probability, 4),
                "guardrail": {
                    "action": "continue" if probability < 0.3 else "review",
                    "should_continue": probability < 0.7,
                },
                "requires_auth": False,
            }
        return {
            "ok": True,
            "mode": "local",
            "workflow_id": workflow_id,
            "event_id": f"local_evt_{uuid.uuid4().hex}",
            "requires_auth": False,
        }


@dataclass
class WorkflowMonitor:
    monitor: ReliabilityMonitor
    workflow_name: str
    workflow_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_stage: Optional[str] = None
    started_ms: int = field(default_factory=_now_ms)
    completed: bool = False

    def __enter__(self) -> "WorkflowMonitor":
        response = self.monitor._send(
            "start_workflow",
            {
                "project_name": self.monitor.project_name,
                "workflow_name": self.workflow_name,
                "workflow_id": self.workflow_id,
                "metadata": self.metadata,
            },
        )
        if response.get("workflow_id"):
            self.workflow_id = response["workflow_id"]
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc is not None:
            self.log_error(
                "exception",
                "".join(traceback.format_exception_only(exc_type, exc)).strip(),
                fatal=True,
            )
            self.complete(success=False, confidence=0.0)
            return False
        if not self.completed:
            self.complete(success=True, confidence=1.0)
        return False

    def track_stage(
        self,
        stage_name: str,
        status: str = "started",
        success: Optional[bool] = None,
        latency_ms: Optional[int] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.current_stage = stage_name
        payload: Dict[str, Any] = {
            "workflow_id": self.workflow_id,
            "stage_name": stage_name,
            "status": status,
            "metadata": metadata or {},
        }
        if success is not None:
            payload["success"] = success
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        if confidence is not None:
            payload["confidence"] = confidence
        return self.monitor._send("track_stage", payload)

    def log_model_call(
        self,
        model: str,
        success: bool,
        latency_ms: int,
        confidence: Optional[float] = None,
        stage_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "workflow_id": self.workflow_id,
            "model": model,
            "success": success,
            "latency_ms": latency_ms,
            "stage_name": stage_name or self.current_stage,
            "metadata": metadata or {},
        }
        if confidence is not None:
            payload["confidence"] = confidence
        return self.monitor._send("log_model_call", payload)

    def log_tool_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: int,
        result_count: Optional[int] = None,
        confidence: Optional[float] = None,
        stage_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "workflow_id": self.workflow_id,
            "tool_name": tool_name,
            "success": success,
            "latency_ms": latency_ms,
            "stage_name": stage_name or self.current_stage,
            "metadata": metadata or {},
        }
        if result_count is not None:
            payload["result_count"] = result_count
        if confidence is not None:
            payload["confidence"] = confidence
        return self.monitor._send("log_tool_call", payload)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        fatal: bool = False,
        stage_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.monitor._send(
            "log_error",
            {
                "workflow_id": self.workflow_id,
                "error_type": error_type,
                "error_message": error_message,
                "stage_name": stage_name or self.current_stage,
                "fatal": fatal,
                "metadata": metadata or {},
            },
        )

    def predict_failure(self) -> Dict[str, Any]:
        return self.monitor.predict_failure(self.workflow_id)

    def apply_guardrail(self) -> Dict[str, Any]:
        return self.monitor.apply_guardrail(self.workflow_id)

    def complete(
        self,
        success: bool,
        confidence: float,
        total_latency_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.completed = True
        return self.monitor.complete_workflow(
            self.workflow_id,
            success=success,
            confidence=confidence,
            total_latency_ms=total_latency_ms,
            metadata=metadata or {},
        )
