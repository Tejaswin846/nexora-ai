from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.services.blob_storage import BlobStorage, tenant_blob_path
from backend.services.message_schema import WorkflowJobMessage
from worker.handlers.workflow import process_workflow_job


@dataclass(frozen=True)
class ProcessResult:
    status: str
    artifact_path: str
    duplicate: bool


class WorkerProcessor:
    def __init__(
        self,
        storage: BlobStorage,
        handler: Callable[[WorkflowJobMessage], dict[str, Any]] = process_workflow_job,
    ) -> None:
        self.storage = storage
        self.handler = handler

    def process(self, message: WorkflowJobMessage) -> ProcessResult:
        artifact_path = tenant_blob_path(
            message.organization_id,
            message.project_id,
            "jobs",
            f"{message.job_id}.json",
        )
        marker_path = tenant_blob_path(
            message.organization_id,
            message.project_id,
            "idempotency",
            f"{message.job_id}.json",
        )
        if self.storage.exists("workflow-artifacts", marker_path):
            return ProcessResult("already_processed", artifact_path, True)

        result = self.handler(message)
        artifact = {
            "schema_version": "1",
            "job_id": str(message.job_id),
            "correlation_id": str(message.correlation_id),
            "organization_id": message.organization_id,
            "project_id": message.project_id,
            "result": result,
        }
        self.storage.upload_json("workflow-artifacts", artifact_path, artifact, overwrite=False)
        self.storage.upload_json(
            "workflow-artifacts",
            marker_path,
            {"job_id": str(message.job_id), "artifact_path": artifact_path},
            overwrite=False,
        )
        return ProcessResult("processed", artifact_path, False)
