from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BICEP = ROOT / "infra" / "bicep"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_required_bicep_modules_exist() -> None:
    modules = {
        "container-registry.bicep",
        "container-apps-environment.bicep",
        "container-app-api.bicep",
        "container-app-worker.bicep",
        "service-bus.bicep",
        "blob-storage.bicep",
        "api-management.bicep",
        "static-web-app.bicep",
        "front-door.bicep",
        "waf-policy.bicep",
        "identities.bicep",
        "role-assignments.bicep",
        "log-analytics.bicep",
    }
    actual = {path.name for path in (BICEP / "modules").glob("*.bicep")}
    assert modules <= actual


def test_staging_parameters_do_not_contain_secret_values() -> None:
    parameters = read("infra/bicep/parameters/staging.bicepparam")
    forbidden = ("SUPABASE", "password", "connectionString", "SharedAccessKey", "clientSecret")
    assert not any(value.lower() in parameters.lower() for value in forbidden)


def test_registry_and_images_use_managed_identity() -> None:
    registry = read("infra/bicep/modules/container-registry.bicep")
    api = read("infra/bicep/modules/container-app-api.bicep")
    worker = read("infra/bicep/modules/container-app-worker.bicep")
    assert "adminUserEnabled: false" in registry
    assert "identity: identityId" in api
    assert "identity: identityId" in worker


def test_worker_has_no_ingress_and_uses_service_bus_identity_scaling() -> None:
    worker = read("infra/bicep/modules/container-app-worker.bicep")
    assert "ingress:" not in worker
    assert "type: 'azure-servicebus'" in worker
    assert "identity: identityId" in worker
    assert "minReplicas: minReplicas" in worker
    assert "maxReplicas: maxReplicas" in worker


def test_service_bus_safety_configuration() -> None:
    service_bus = read("infra/bicep/modules/service-bus.bicep")
    assert "name: 'Standard'" in service_bus
    assert "disableLocalAuth: true" in service_bus
    assert "requiresDuplicateDetection: true" in service_bus
    assert "deadLetteringOnMessageExpiration: true" in service_bus
    assert "maxDeliveryCount: 5" in service_bus


def test_blob_storage_is_private_and_recoverable() -> None:
    storage = read("infra/bicep/modules/blob-storage.bicep")
    assert "allowBlobPublicAccess: false" in storage
    assert "allowSharedKeyAccess: false" in storage
    assert "supportsHttpsTrafficOnly: true" in storage
    assert "isVersioningEnabled: true" in storage
    assert "publicAccess: 'None'" in storage


def test_front_door_waf_and_apim_are_explicitly_staging_only() -> None:
    front_door = read("infra/bicep/modules/front-door.bicep")
    waf = read("infra/bicep/modules/waf-policy.bicep")
    apim = read("infra/bicep/modules/api-management.bicep")
    policy = read("infra/bicep/modules/api-management-policy.bicep")
    assert "Premium_AzureFrontDoor" in front_door
    assert "mode: 'Detection'" in waf
    assert "Microsoft_DefaultRuleSet" in waf
    assert "name: 'Developer'" in apim
    assert "X-Azure-FDID" in policy
    assert "rate-limit-by-key" in policy


def test_deployment_has_an_explicit_fixed_cost_gate() -> None:
    deploy = read("infra/scripts/deploy-staging.ps1")
    workflow = read(".github/workflows/azure-staging.yml")
    assert "ApproveFixedMonthlyCost" in deploy
    assert "AZURE_PILLAR1_FIXED_COST_APPROVED" in deploy
    assert "AZURE_PILLAR1_FIXED_COST_APPROVED" in workflow
    assert "id-token: write" in workflow


def test_rollback_and_destroy_preserve_data_by_default() -> None:
    rollback = read("infra/scripts/rollback-staging.ps1")
    destroy = read("infra/scripts/destroy-staging.ps1")
    assert "az group delete" not in rollback
    assert "az servicebus queue delete" not in rollback
    assert "az storage" not in rollback
    assert "Automated deletion remains intentionally disabled" in destroy


def test_container_builds_are_non_root_and_exclude_sensitive_files() -> None:
    api = read("Dockerfile.api")
    worker = read("Dockerfile.worker")
    ignore = read(".dockerignore")
    assert "USER 10001:10001" in api
    assert "USER 10001:10001" in worker
    assert "**/.env*" in ignore
    assert "**/*.db" in ignore
    assert "Software/*_report.md" in ignore
