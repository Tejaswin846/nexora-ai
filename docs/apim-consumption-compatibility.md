# APIM Consumption Compatibility

Verified: 2026-07-12 against the current Microsoft API Management feature and policy documentation.

## Decision

API Management Consumption is **disabled for lean staging**. It supports nearly all required gateway behavior, but it does not support `rate-limit-by-key` or `quota-by-key`. The current Pillar 1 policy keys throttling by organization ID with client IP fallback, so replacing it with subscription-scoped `rate-limit` would change the required isolation behavior.

The staging fallback is therefore:

`Front Door Standard -> Container Apps API -> Service Bus -> Container Apps worker -> Blob Storage`

Front Door provides per-client-IP custom WAF rate limiting. FastAPI provides temporary organization/IP fixed-window limiting, origin validation, correlation IDs, request-size checks, a 60-second timeout, CORS, and standardized JSON errors. Production can insert APIM without changing application routes.

## Feature matrix

| Requirement | Consumption result | Evidence or limitation | Alternative in lean staging |
|---|---|---|---|
| OpenAPI import | Supported | Microsoft documents OpenAPI import for all APIM tiers. | FastAPI continues publishing `/openapi.json`. |
| Backend routing | Supported | `set-backend-service` and `forward-request` support the Consumption gateway. | Front Door routes directly to the Container App origin. |
| Correlation ID creation/forwarding | Supported | `set-variable` and `set-header` are available in Consumption. | FastAPI creates or preserves `X-Correlation-ID`. |
| Request-size restriction | Supported | `choose`, header checks, and content validation policies are supported. | FastAPI rejects declared bodies above 1 MiB. |
| Request timeout | Supported with limitations | `forward-request timeout` is supported; values above 240 seconds may not be honored. | FastAPI applies a 60-second timeout. |
| Rate limiting/quota | **Unsupported for the required key** | Microsoft explicitly excludes `rate-limit-by-key` and `quota-by-key` from Consumption. Subscription-scoped rate limiting is not equivalent to organization/IP keys. | Front Door custom IP rate limit plus temporary FastAPI organization/IP limiter. |
| Header transformation | Supported | `set-header` applies to the Consumption gateway. | Front Door marks the edge path; FastAPI strips server-identifying response headers. |
| CORS | Supported | The `cors` policy supports Consumption. | Exact origins remain enforced by FastAPI. |
| JWT validation | Supported | `validate-jwt` supports Consumption. | Existing FastAPI/Supabase authentication remains authoritative. |
| Subscription keys | Supported | APIM subscriptions apply to all tiers. They are not currently required by this API. | No browser-visible gateway key is introduced. |
| Standardized errors | Supported | `choose`, `return-response`, and `on-error` are supported. | FastAPI emits a stable `{error:{code,message,correlation_id}}` shape. |
| Azure Monitor metrics | Supported | Consumption publishes Azure Monitor metrics. | Front Door and Container Apps diagnostics remain enabled. |
| Log Analytics request logs | Unsupported | The tier comparison excludes APIM Azure Monitor/Log Analytics request logs in Consumption; Application Insights request logs are supported. | No APIM is deployed; request bodies, cookies, and authorization headers are not logged. |

## Production requirement

Re-enable APIM only with a tier that supports `rate-limit-by-key` and has a production SLA. `production.bicepparam` recommends APIM Standard. Developer remains an available parameter value only to preserve the previously prepared non-production configuration; it is not recommended for production.

## Sources

- [API Management tier comparison](https://learn.microsoft.com/azure/api-management/api-management-features)
- [API Management policy support matrix](https://learn.microsoft.com/azure/api-management/api-management-policies)
- [Custom key-based throttling limitation](https://learn.microsoft.com/azure/api-management/api-management-sample-flexible-throttling)
- [OpenAPI import](https://learn.microsoft.com/azure/api-management/import-api-from-oas)
- [Forward request timeout](https://learn.microsoft.com/azure/api-management/forward-request-policy)
- [JWT validation](https://learn.microsoft.com/azure/api-management/validate-jwt-policy)
- [APIM subscriptions](https://learn.microsoft.com/azure/api-management/api-management-subscriptions)
