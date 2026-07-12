# Azure Pillar 1 Connections

| Source | Destination | Protocol | Authentication | Required role | Environment variables | Health check | Failure and retry behavior |
|---|---|---|---|---|---|---|---|
| Browser | Front Door frontend route | HTTPS | Existing application auth where required | None | `PUBLIC_BASE_URL` | `GET /` | Browser retry; static assets cached |
| Front Door | Static Web Apps | HTTPS | Origin host validation and TLS | None | None | `GET /index.html` | Front Door origin health and retry |
| Browser | Front Door `/api/*` | HTTPS | Supabase/application auth | None | `API_BASE_URL` | `GET /health/live` | API errors returned with correlation ID |
| Front Door | API Management | HTTPS | Exact platform-generated `X-Azure-FDID` | None | None | `GET /health/live` | APIM returns 403 for direct bypass |
| API Management | Container Apps API | HTTPS | APIM named-value backend secret | None | `APIM_BACKEND_SHARED_SECRET` | `GET /health/live` | 60-second timeout; no unsafe automatic write retry |
| Container Apps API | Service Bus `workflow-jobs` | AMQP over TLS | User-assigned managed identity | Azure Service Bus Data Sender | `AZURE_SERVICE_BUS_NAMESPACE`, `AZURE_SERVICE_BUS_QUEUE_NAME`, `AZURE_CLIENT_ID` | Readiness verifies configuration | Duplicate detection uses `job_id`; send failures return 503 |
| Service Bus | Container Apps worker | AMQP over TLS | User-assigned managed identity | Azure Service Bus Data Receiver | Same Service Bus variables | Queue length drives KEDA | Temporary failures abandon; invalid/permanent failures dead-letter; max delivery 5 |
| API | Blob Storage | HTTPS | User-assigned managed identity | Storage Blob Data Contributor | `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_CLIENT_ID` | Authorized artifact read | Missing artifacts return 404; tenant path is derived server-side |
| Worker | Blob Storage | HTTPS | User-assigned managed identity | Storage Blob Data Contributor | Same Blob variables | Artifact and idempotency marker writes | Message completes only after successful writes |
| API and worker | ACR | HTTPS | User-assigned managed identity | AcrPull | Registry configured by Container Apps | Revision image pull status | Failed image pull prevents unhealthy revision promotion |
| GitHub Actions | Azure Resource Manager | HTTPS | OIDC federated credential | Bootstrap deployment roles supplied separately | GitHub environment IDs | Bicep validation | Workflow stops on critical failure |
| GitHub Actions | ACR | HTTPS | Azure OIDC session | AcrPush | Deployment outputs | Push digest | SHA tag required; no `latest`-only deployment |
| API | Supabase/Postgres | TLS/HTTPS | Existing Supabase credentials | Existing Supabase roles and RLS | `SUPABASE_URL`, Supabase keys, `DATABASE_URL` | `/health/ready` | Startup/readiness fails closed in staging |

## Message envelope

Every queue message uses schema version `1`, UUID job and correlation identifiers, tenant identifiers, job type, timezone-aware creation time, payload, and metadata. Unknown fields and sensitive key names are rejected before send and again before processing.

## Correlation

Front Door forwards headers, APIM creates or preserves `X-Correlation-ID`, the API places it in the Service Bus envelope, and the worker writes it into the Blob artifact. Authorization headers, cookies, and secret values are not logged.
