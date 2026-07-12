# Azure Pillar 1 Test Results

Test date: 2026-07-12

## Completed locally

| Test | Result |
|---|---|
| Python syntax compilation for API, services, worker | Passed |
| Pillar 1 focused unit and infrastructure tests | 21 passed |
| Live health endpoint | Passed |
| Readiness fail-closed behavior | Passed |
| Build-aware version endpoint | Passed |
| OpenAPI availability | Passed |
| Queue message validation and secret-key rejection | Passed |
| Valid and invalid job submission | Passed |
| Blob upload/download and tenant path rejection | Passed |
| Worker success, retryable failure, permanent failure | Passed |
| Idempotent duplicate processing | Passed |
| Frontend backend-secret assignment scan | Passed |
| Bicep compilation | Passed |
| Azure subscription-scope template validation | Passed; no resources created |
| Ruff focused lint | Passed |
| PowerShell script parsing | Passed |
| GitHub Actions YAML parsing | Passed |

## Not yet executed

The following require approved Azure staging resources and must not be claimed as working yet:

- Docker image build and runtime health; Docker is not installed on the current machine and remains a CI check.
- ACR managed-identity pull.
- APIM OpenAPI import and policy execution.
- Front Door frontend and API routing.
- Exact `X-Azure-FDID` enforcement.
- Service Bus send, receive, retry, dead-letter, and KEDA scaling.
- Managed-identity Blob upload/download.
- Static Web Apps deployment and direct hostname load.
- Complete correlation path across Front Door, APIM, API, queue, worker, and Blob.
- WAF legitimate-traffic findings.
- Render availability confirmation through authenticated Render tooling.

No paid AI calls were made. No Azure resource was created or changed during these tests.
