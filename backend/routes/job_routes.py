from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

try:
    from dependencies import get_current_user, get_runtime_module
    from services.blob_storage import AzureBlobStorage, BlobStorage, InMemoryBlobStorage, tenant_blob_path
    from services.job_queue import JobQueue, get_job_queue
    from services.message_schema import IDENTIFIER_PATTERN, WorkflowJobMessage
except Exception:
    from ..dependencies import get_current_user, get_runtime_module
    from ..services.blob_storage import AzureBlobStorage, BlobStorage, InMemoryBlobStorage, tenant_blob_path
    from ..services.job_queue import JobQueue, get_job_queue
    from ..services.message_schema import IDENTIFIER_PATTERN, WorkflowJobMessage


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobSubmission(BaseModel):
    job_type: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None


@dataclass(frozen=True)
class AuthorizedJobTenant:
    organization_id: str
    project_id: str


def authorize_job_tenant(
    x_organization_id: str = Header(...),
    x_project_id: str = Header(...),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> AuthorizedJobTenant:
    user_id = str(current_user.get("id") or "").strip()
    if not IDENTIFIER_PATTERN.fullmatch(user_id):
        raise HTTPException(status_code=403, detail="The authenticated account cannot be used as a job tenant.")
    if x_organization_id.strip() != user_id:
        raise HTTPException(status_code=403, detail="The requested organization does not belong to this account.")

    try:
        projects = get_runtime_module().projects_for_user(user_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Project authorization is unavailable.") from error

    project_id = x_project_id.strip()
    owned_project_ids = {
        str(project.get("id") or "")
        for project in projects
        if isinstance(project, dict)
    }
    if project_id not in owned_project_ids:
        raise HTTPException(status_code=403, detail="The requested project does not belong to this account.")
    return AuthorizedJobTenant(organization_id=user_id, project_id=project_id)


@lru_cache(maxsize=1)
def get_blob_storage() -> BlobStorage:
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "").strip()
    environment = os.getenv("NEXORA_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower()
    if account_url:
        return AzureBlobStorage(account_url)
    if environment in {"staging", "production"}:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL is required in staging and production.")
    return InMemoryBlobStorage()


@router.post("", status_code=202)
def submit_job(
    request: JobSubmission,
    response: Response,
    tenant: AuthorizedJobTenant = Depends(authorize_job_tenant),
    x_correlation_id: str | None = Header(default=None),
) -> dict[str, str]:
    try:
        correlation_id = request.correlation_id or (UUID(x_correlation_id) if x_correlation_id else uuid4())
        message = WorkflowJobMessage(
            job_id=uuid4(),
            correlation_id=correlation_id,
            organization_id=tenant.organization_id,
            project_id=tenant.project_id,
            job_type=request.job_type,
            created_at=datetime.now(timezone.utc),
            payload=request.payload,
            metadata=request.metadata,
        )
        queue: JobQueue = get_job_queue()
        queue.enqueue(message)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Job queue is unavailable.") from error

    response.headers["X-Correlation-ID"] = str(message.correlation_id)
    return {
        "status": "accepted",
        "job_id": str(message.job_id),
        "correlation_id": str(message.correlation_id),
    }


@router.get("/{job_id}/artifact")
def get_job_artifact(
    job_id: UUID,
    tenant: AuthorizedJobTenant = Depends(authorize_job_tenant),
) -> dict[str, Any]:
    try:
        blob_name = tenant_blob_path(tenant.organization_id, tenant.project_id, "jobs", f"{job_id}.json")
        return get_blob_storage().download_json("workflow-artifacts", blob_name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Job artifact not found.") from error
