# Azure Pillar 1 Test Results

Test date: 2026-07-12

## Passed locally

| Test | Result |
|---|---|
| Full repository suite | 95 passed |
| Focused Pillar 1 runtime/infrastructure suite | 26 passed |
| GitHub clean-checkout infrastructure contract suite | Pending rerun; full local suite relies on pre-existing untracked application modules |
| Ruff focused lint | Passed |
| Python compilation | Passed |
| Bicep main template compilation/lint | Passed |
| Staging and production parameter compilation | Passed |
| Authenticated Azure foundation validation | Passed; no resources created |
| Authenticated Azure full-workload validation | Passed; no resources created |
| Azure full-workload what-if | Succeeded; 32 create, 0 modify, 0 delete, 6 runtime-ID RBAC evaluations unsupported |
| PowerShell syntax | Passed |
| GitHub Actions YAML syntax | Passed |
| APIM Consumption compatibility review | Passed; unsupported key policy correctly activates fallback |
| Front Door Standard/custom-only WAF assertions | Passed |
| Lean SKU, LRS, scale-to-zero, and replica-cap assertions | Passed |
| Gateway bypass, request-size, correlation, and fallback rate-limit tests | Passed |
| Secret-pattern scan | Passed |
| GitHub Actions API Docker build | Pending branch push |
| GitHub Actions worker Docker build/runtime import | Pending branch push |

## Not claimed

No Azure resource exists, so no end-to-end deployment success or live connection is claimed. After approval, deployment must still verify ACR pull, Front Door routing and origin protection, Container Apps cold starts, Service Bus send/receive/dead-letter/KEDA behavior, Blob managed identity, Static Web Apps, correlation across the entire flow, WAF findings, and rollback.

Render, Nexora, production DNS, and Supabase were not modified. No paid AI call was made.
