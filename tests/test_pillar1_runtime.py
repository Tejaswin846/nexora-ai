from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.config import Settings
from backend.gateway_protection import gateway_protection_middleware
from backend.routes import health_routes, job_routes
from backend.services.blob_storage import InMemoryBlobStorage, tenant_blob_path
from backend.services.message_schema import WorkflowJobMessage
from worker.handlers.workflow import PermanentJobError, RetryableJobError
from worker.processor import WorkerProcessor


def build_message(**overrides) -> WorkflowJobMessage:
    values = {
        "job_id": uuid4(),
        "correlation_id": uuid4(),
        "organization_id": "test-organization",
        "project_id": "test-project",
        "job_type": "staging_smoke_test",
        "created_at": datetime.now(timezone.utc),
        "payload": {"probe": "pillar-1"},
        "metadata": {},
    }
    values.update(overrides)
    return WorkflowJobMessage(**values)


def health_client(settings: Settings) -> TestClient:
    app = FastAPI()
    app.include_router(health_routes.router)
    app.dependency_overrides[health_routes.get_runtime_settings] = lambda: settings
    return TestClient(app)


def test_live_health_and_openapi_are_available() -> None:
    client = health_client(Settings(_env_file=None, env="development"))
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/openapi.json").status_code == 200


def test_readiness_fails_closed_when_staging_configuration_is_missing() -> None:
    client = health_client(
        Settings(
            _env_file=None,
            env="staging",
            database_url="",
            supabase_url="",
            supabase_anon_key="",
            supabase_service_role_key="",
            upstash_redis_rest_url="",
            upstash_redis_rest_token="",
        )
    )
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "AZURE_SERVICE_BUS_NAMESPACE" in response.json()["missing_configuration"]


def test_version_contains_build_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
    monkeypatch.setenv("BUILD_TIMESTAMP", "2026-07-12T00:00:00Z")
    client = health_client(Settings(_env_file=None, env="staging"))
    payload = client.get("/version").json()
    assert payload == {
        "version": "1.2.3",
        "git_commit_sha": "abc1234",
        "environment": "staging",
        "build_timestamp": "2026-07-12T00:00:00Z",
    }


def test_message_schema_rejects_sensitive_keys() -> None:
    with pytest.raises(ValidationError):
        build_message(payload={"api_key": "must-not-enter-the-queue"})


def test_message_schema_rejects_invalid_tenant_identifier() -> None:
    with pytest.raises(ValidationError):
        build_message(organization_id="../../other-tenant")


def test_valid_job_submission_sets_correlation_header(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQueue:
        def __init__(self) -> None:
            self.messages = []

        def enqueue(self, message: WorkflowJobMessage) -> None:
            self.messages.append(message)

    queue = FakeQueue()
    monkeypatch.setattr(job_routes, "get_job_queue", lambda: queue)
    monkeypatch.setattr(
        job_routes,
        "get_runtime_module",
        lambda: type("ProjectStore", (), {"projects_for_user": staticmethod(lambda _user_id: [{"id": "test-project"}])}),
    )
    app = FastAPI()
    app.include_router(job_routes.router)
    app.dependency_overrides[job_routes.get_current_user] = lambda: {"id": "test-org"}
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        headers={"X-Organization-ID": "test-org", "X-Project-ID": "test-project"},
        json={"job_type": "staging_smoke_test", "payload": {"probe": True}},
    )

    assert response.status_code == 202
    assert response.headers["x-correlation-id"] == response.json()["correlation_id"]
    assert len(queue.messages) == 1
    assert queue.messages[0].organization_id == "test-org"
    assert queue.messages[0].project_id == "test-project"


def test_invalid_job_submission_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_routes, "get_job_queue", lambda: None)
    monkeypatch.setattr(
        job_routes,
        "get_runtime_module",
        lambda: type("ProjectStore", (), {"projects_for_user": staticmethod(lambda _user_id: [{"id": "test-project"}])}),
    )
    app = FastAPI()
    app.include_router(job_routes.router)
    app.dependency_overrides[job_routes.get_current_user] = lambda: {"id": "test-org"}
    client = TestClient(app)
    response = client.post(
        "/api/jobs",
        headers={"X-Organization-ID": "../escape", "X-Project-ID": "test-project"},
        json={"job_type": "staging_smoke_test"},
    )
    assert response.status_code == 403


def test_job_submission_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    class RejectAnonymous:
        def __call__(self) -> dict:
            raise HTTPException(status_code=401, detail="Login required.")

    app = FastAPI()
    app.include_router(job_routes.router)
    app.dependency_overrides[job_routes.get_current_user] = RejectAnonymous()
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        headers={"X-Organization-ID": "attacker", "X-Project-ID": "victim-project"},
        json={"job_type": "staging_smoke_test"},
    )

    assert response.status_code == 401


def test_job_submission_rejects_spoofed_tenant_and_project(monkeypatch: pytest.MonkeyPatch) -> None:
    class QueueMustNotRun:
        def enqueue(self, _message: WorkflowJobMessage) -> None:
            raise AssertionError("unauthorized job reached the queue")

    monkeypatch.setattr(job_routes, "get_job_queue", lambda: QueueMustNotRun())
    monkeypatch.setattr(
        job_routes,
        "get_runtime_module",
        lambda: type("ProjectStore", (), {"projects_for_user": staticmethod(lambda _user_id: [{"id": "alice-project"}])}),
    )
    app = FastAPI()
    app.include_router(job_routes.router)
    app.dependency_overrides[job_routes.get_current_user] = lambda: {"id": "alice-user"}
    client = TestClient(app)

    wrong_organization = client.post(
        "/api/jobs",
        headers={"X-Organization-ID": "bob-user", "X-Project-ID": "alice-project"},
        json={"job_type": "staging_smoke_test"},
    )
    wrong_project = client.post(
        "/api/jobs",
        headers={"X-Organization-ID": "alice-user", "X-Project-ID": "bob-project"},
        json={"job_type": "staging_smoke_test"},
    )

    assert wrong_organization.status_code == 403
    assert wrong_project.status_code == 403


def test_job_artifact_access_is_tenant_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = InMemoryBlobStorage()
    job_id = uuid4()
    owned_path = tenant_blob_path("alice-user", "alice-project", "jobs", f"{job_id}.json")
    storage.upload_json("workflow-artifacts", owned_path, {"job_id": str(job_id), "result": "private"})
    monkeypatch.setattr(job_routes, "get_blob_storage", lambda: storage)
    monkeypatch.setattr(
        job_routes,
        "get_runtime_module",
        lambda: type("ProjectStore", (), {"projects_for_user": staticmethod(lambda _user_id: [{"id": "alice-project"}])}),
    )
    app = FastAPI()
    app.include_router(job_routes.router)
    app.dependency_overrides[job_routes.get_current_user] = lambda: {"id": "alice-user"}
    client = TestClient(app)

    allowed = client.get(
        f"/api/jobs/{job_id}/artifact",
        headers={"X-Organization-ID": "alice-user", "X-Project-ID": "alice-project"},
    )
    cross_tenant = client.get(
        f"/api/jobs/{job_id}/artifact",
        headers={"X-Organization-ID": "bob-user", "X-Project-ID": "alice-project"},
    )
    cross_project = client.get(
        f"/api/jobs/{job_id}/artifact",
        headers={"X-Organization-ID": "alice-user", "X-Project-ID": "bob-project"},
    )

    assert allowed.status_code == 200
    assert allowed.json()["result"] == "private"
    assert cross_tenant.status_code == 403
    assert cross_project.status_code == 403


def test_blob_upload_download_and_tenant_path_validation() -> None:
    storage = InMemoryBlobStorage()
    path = tenant_blob_path("org", "project", "jobs", "job.json")
    storage.upload_json("workflow-artifacts", path, {"ok": True})
    assert storage.download_json("workflow-artifacts", path) == {"ok": True}
    with pytest.raises(ValueError):
        tenant_blob_path("org", "../another-project", "jobs", "job.json")


def test_worker_processes_each_job_once() -> None:
    storage = InMemoryBlobStorage()
    processor = WorkerProcessor(storage)
    message = build_message()

    first = processor.process(message)
    second = processor.process(message)

    assert first.status == "processed"
    assert first.duplicate is False
    assert second.status == "already_processed"
    assert second.duplicate is True
    artifact = storage.download_json("workflow-artifacts", first.artifact_path)
    assert artifact["correlation_id"] == str(message.correlation_id)


def test_worker_propagates_retryable_and_permanent_failures() -> None:
    message = build_message()

    def temporary_failure(_message: WorkflowJobMessage) -> dict:
        raise RetryableJobError("temporary")

    def permanent_failure(_message: WorkflowJobMessage) -> dict:
        raise PermanentJobError("permanent")

    with pytest.raises(RetryableJobError):
        WorkerProcessor(InMemoryBlobStorage(), temporary_failure).process(message)
    with pytest.raises(PermanentJobError):
        WorkerProcessor(InMemoryBlobStorage(), permanent_failure).process(message)


def test_frontend_does_not_contain_backend_secret_assignments() -> None:
    frontend = Path("frontend")
    content = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in frontend.glob("*.*"))
    forbidden = ("SUPABASE_SERVICE_ROLE_KEY=", "AZURE_CLIENT_SECRET=", "DATABASE_URL=postgres")
    assert not any(value in content for value in forbidden)


def gateway_client() -> TestClient:
    app = FastAPI()
    app.middleware("http")(gateway_protection_middleware)

    @app.post("/api/test")
    def protected_route() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_front_door_fallback_rejects_direct_origin_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPROVED_GATEWAY_MODE", "frontdoor")
    monkeypatch.setenv("EXPECTED_AZURE_FRONT_DOOR_ID", "expected-fdid")
    client = gateway_client()

    rejected = client.post("/api/test")
    accepted = client.post(
        "/api/test",
        headers={"X-Azure-FDID": "expected-fdid", "X-Software-Edge": "azure-front-door"},
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert accepted.headers["x-correlation-id"]


def test_front_door_fallback_enforces_request_size_and_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPROVED_GATEWAY_MODE", "frontdoor")
    monkeypatch.setenv("EXPECTED_AZURE_FRONT_DOOR_ID", "expected-fdid")
    monkeypatch.setenv("STAGING_MAX_REQUEST_BYTES", "5")
    monkeypatch.setenv("STAGING_RATE_LIMIT_CALLS", "1")
    client = gateway_client()
    headers = {
        "X-Azure-FDID": "expected-fdid",
        "X-Software-Edge": "azure-front-door",
        "X-Organization-ID": f"test-{uuid4()}",
    }

    too_large = client.post("/api/test", headers=headers, content="123456")
    first = client.post("/api/test", headers=headers)
    second = client.post("/api/test", headers=headers)

    assert too_large.status_code == 413
    assert first.status_code == 200
    assert second.status_code == 429
