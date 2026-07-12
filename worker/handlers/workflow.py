from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.message_schema import WorkflowJobMessage


class RetryableJobError(RuntimeError):
    pass


class PermanentJobError(RuntimeError):
    pass


EXISTING_EXPORTS = {
    "guardrail_effectiveness": Path("Software/data/guardrail_effectiveness_output.json"),
    "reliability_prediction": Path("Software/data/reliability_prediction_output.json"),
    "tool_reliability": Path("Software/data/tool_reliability_benchmark_output.json"),
    "workflow_reliability": Path("Software/data/workflow_reliability_analysis_output.json"),
}


def process_workflow_job(message: WorkflowJobMessage) -> dict[str, Any]:
    if message.job_type == "staging_smoke_test":
        return {
            "status": "processed",
            "job_type": message.job_type,
            "payload": message.payload,
        }

    if message.job_type == "benchmark_export":
        export_name = str(message.payload.get("export_name", ""))
        source = EXISTING_EXPORTS.get(export_name)
        if source is None:
            raise PermanentJobError("unsupported benchmark export")
        if not source.exists():
            raise RetryableJobError("benchmark export is not available yet")
        return {
            "status": "processed",
            "job_type": message.job_type,
            "export_name": export_name,
            "result": json.loads(source.read_text(encoding="utf-8")),
        }

    raise PermanentJobError("unsupported job type")
