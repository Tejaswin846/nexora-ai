# Azure Pillar 1 Security

## Staging controls

- Front Door Standard uses custom WAF and rate-limit rules in Detection mode. Managed WAF rule sets are not configured or claimed as tested.
- The public Container App origin allows only probes without gateway proof. Other routes require the exact Front Door profile ID and an overwritten edge marker, compared without timing leakage.
- FastAPI applies a 1 MiB declared-body limit, 60-second timeout, organization/IP rate limit, exact CORS origins, correlation IDs, and standardized errors.
- The worker has no ingress and uses managed identity to receive queue messages and write blobs.
- Storage public access and shared-key authentication are disabled; cross-tenant replication is disabled; blob paths are tenant-rooted.
- Service Bus local authentication is disabled. Queue messages reject sensitive key names and the worker is idempotent.
- ACR admin authentication is disabled; images use immutable Git SHA tags.
- GitHub uses environment-restricted OIDC. No Azure client secret is requested.

## Secret handling

Application credentials are passed only as secure Bicep parameters into Container Apps secrets. No values are stored in `.bicepparam`, workflow output, source code, or docs. Supabase remains external and unchanged.

Key Vault is not provisioned by this Pillar 1 revision. Before production, migrate Container App secrets to Key Vault references and define rotation ownership.

## Telemetry privacy

Request logs contain route, status, latency, request/correlation ID, and authenticated IDs when available. They do not include request bodies, response bodies, authorization headers, cookies, prompts, API keys, or connection strings. Successful request logs are sampled at 25%; failures remain logged.

## Remaining risks

- The temporary FastAPI limiter is process-local, so the effective organization limit can multiply across two replicas. Front Door still provides per-IP edge rate limiting. Production requires APIM Standard or another distributed limiter.
- Detection mode logs but does not block WAF matches.
- Front Door Standard has no managed OWASP/DRS coverage.
- Scale-to-zero creates cold-start latency.
- The Log Analytics alert has no notification action until an approved operations contact is supplied.
- The current subscription-scope deployment wrapper needs narrowly defined subscription deployment permission; every run must retain what-if review and GitHub Environment approval.
