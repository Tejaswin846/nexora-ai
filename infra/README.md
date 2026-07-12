# Azure Pillar 1 Infrastructure

This directory contains the staging-only Azure Bicep implementation and guarded operational scripts.

## Safety gate

The requested managed Front Door WAF rules require Azure Front Door Premium. Together with APIM Developer, Service Bus Standard, and ACR Basic, the predictable fixed baseline is approximately USD 393/month before usage, tax, and discounts.

`deploy-staging.ps1` refuses to deploy unless both conditions are met:

```powershell
$env:AZURE_PILLAR1_FIXED_COST_APPROVED = "true"
./infra/scripts/deploy-staging.ps1 -ApproveFixedMonthlyCost
```

Do not run that command until the cost report has explicit approval.

## Layout

- `bicep/main.bicep`: subscription-scope composition and staging resource group.
- `bicep/modules/`: one module per Azure service or role boundary.
- `bicep/parameters/staging.bicepparam`: non-secret staging defaults.
- `scripts/validate.ps1`: local Bicep build and read-only deployment validation.
- `scripts/deploy-staging.ps1`: guarded foundation, image, workload, edge, and frontend deployment.
- `scripts/smoke-test.ps1`: complete request-flow smoke test without paid AI calls.
- `scripts/rollback-staging.ps1`: revision, route, and worker rollback without deleting data.
- `scripts/destroy-staging.ps1`: intentionally disabled break-glass placeholder.

## Selected locations

- Regional Azure resources: `centralindia`.
- Static Web Apps: `eastasia`, because the provider does not offer Static Web Apps in India.
- Azure Front Door and WAF: global.

## Deployment sequence

1. Validate Bicep.
2. Deploy the foundation with workloads disabled.
3. Build and push `api:<git-sha>` and `worker:<git-sha>`.
4. Deploy API, worker, APIM Developer, Front Door Premium, and WAF Detection mode.
5. Feed the generated Front Door hostname back into exact CORS configuration.
6. Deploy unchanged frontend files to Static Web Apps.
7. Run the end-to-end smoke test.

No script modifies Render, production DNS, or any resource in the Nexora resource group.
