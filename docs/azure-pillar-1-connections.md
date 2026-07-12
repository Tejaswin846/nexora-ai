# Azure Pillar 1 Connections

| Source | Destination | Protocol/authentication | Health/failure behavior |
|---|---|---|---|
| Browser/client | Front Door Standard | HTTPS | HTTP redirects; WAF Detection logs custom-rule matches |
| Front Door | Static Web Apps Free | HTTPS origin host | `/index.html` probe; static route cached/compressed |
| Front Door | Container Apps API | HTTPS, exact `X-Azure-FDID` plus edge marker | `/health/live` probe; API routes are not cached |
| API | Supabase | Existing HTTPS/Postgres credentials via Container App secrets | Supabase remains the main database; no migration |
| API | Service Bus | Managed identity, Data Sender | Queue envelope preserves correlation ID; no write retry by gateway |
| Service Bus | Worker | Managed identity, Data Receiver/KEDA | Five deliveries then dead letter; application idempotency required |
| API/worker | Blob Storage | Managed identity, Blob Data Contributor | Private tenant-rooted paths; retries only for transient operations |
| Containers/Front Door | Log Analytics | Azure diagnostics/stdout | 30-day retention, sampled request success logs, emergency cap |

APIM is absent in lean staging. In production, Front Door targets APIM and APIM forwards to the same API routes using the existing backend policy module.

Authorization headers, cookies, request bodies, prompts, responses, and secrets are never included in application request logs.
