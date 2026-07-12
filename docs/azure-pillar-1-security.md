# Azure Pillar 1 Security

## Implemented controls

- Separate user-assigned identities for API, worker, and GitHub deployment.
- API receives Service Bus sender only; worker receives Service Bus receiver only.
- API and worker receive Blob data-plane access without storage-account management roles.
- ACR admin and anonymous pull are disabled.
- Service Bus local authentication is disabled and duplicate detection is enabled.
- Storage shared-key access and public Blob access are disabled; TLS 1.2, soft delete, and versioning are enabled.
- Worker has no ingress.
- API bypass is blocked by a constant-time APIM backend header outside health/version/OpenAPI routes.
- APIM validates the exact deployed Front Door ID, creates a correlation ID, limits request size, removes backend headers, and blocks internal route families.
- WAF uses Microsoft Default and Bot Manager rule sets in Detection mode, plus an API abuse rate-limit rule.
- CORS accepts only the generated Static Web Apps and Front Door origins. Wildcard credentialed CORS was removed.
- Images run as UID/GID 10001 and exclude `.env`, databases, logs, reports, tests, and copy artifacts.
- Queue schemas reject credential-like key names recursively.
- Blob paths validate organization, project, category, and filename segments.
- GitHub uses OIDC; no permanent service-principal password is defined.

## Secrets

Pillar 1 follows the attached requirement to defer Key Vault to Pillar 2. Secret values are supplied as secure Bicep parameters and stored as Container Apps secrets or APIM secret named values. No secret values exist in `.bicepparam`, `.env.example`, workflow output, or documentation.

Key Vault migration remains the first Pillar 2 security task. Supabase service-role credentials must never be exposed to Static Web Apps or browser JavaScript.

## Known risks and staging limitations

- Front Door WAF starts in Detection mode; it does not block managed-rule findings until reviewed.
- APIM Developer has no SLA and is not production-ready.
- Static Web Apps Free has no SLA.
- Container Apps, Service Bus, ACR, and Storage remain publicly reachable Azure endpoints protected by identity and application controls; private networking is deferred.
- The direct API hostname intentionally exposes liveness, readiness, version, and OpenAPI for deployment verification.
- Existing Render and Nexora deployments have separate risks and are not changed by Pillar 1.
- The current standalone `Software.app` SQLite database is not used as the production database. Supabase/Postgres remains authoritative.

## WAF promotion criteria

Do not change WAF to Prevention until legitimate frontend, auth, SDK, upload, dashboard, and job flows have passed through Front Door and WAF logs show no required exclusion. Any exclusion must cite a reproduced false positive and the narrowest matching rule and path.
