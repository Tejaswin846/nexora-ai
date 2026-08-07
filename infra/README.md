# Azure Pillar 1 Infrastructure

This directory contains tier-configurable Bicep for lean staging and a separate production recommendation. Nothing deploys on a branch push.

## Profiles

- `bicep/parameters/staging.bicepparam`: Front Door Standard, APIM Consumption selected but disabled after compatibility review, Static Web Apps Free, ACR Basic, Service Bus Standard, Blob LRS, and Container Apps 0-2.
- `bicep/parameters/production.bicepparam`: Front Door Premium, APIM Standard, managed WAF rules, SLA-backed frontend, and nonzero replicas. This profile is not wired to the staging deployment workflow.

Lean staging has a $50.07 fixed baseline, a $50.77 low-traffic estimate, and an $85.40 maximum-expected operating envelope. See `docs/azure-pillar-1-costs-lean-staging.md`.

## Safety gate

The workflow deploy job requires all of the following:

1. Manual `workflow_dispatch` with `deploy=true`.
2. Successful test and Docker build job.
3. `AZURE_PILLAR1_LEAN_STAGING_APPROVED=true`.
4. Approval through the protected GitHub Environment `staging`.
5. OIDC authentication without a client secret.

The script independently requires:

```powershell
$env:AZURE_PILLAR1_LEAN_STAGING_APPROVED = "true"
./infra/scripts/deploy-staging.ps1 -ApproveLeanStagingCost
```

Do not run it until the user sends the exact approval sentence from the final report.

The staging environment must also provide `NEXORA_SMOKE_EMAIL` and
`NEXORA_SMOKE_PASSWORD` secrets for a dedicated test account. The end-to-end
smoke test signs in through the public application, reuses or creates a project
owned by that account, derives the tenant from the session, and verifies
anonymous job submission is rejected before testing the queue and artifact
path.

## Validation

`scripts/validate.ps1` compiles the template and both parameter profiles, then runs read-only Azure validation. Azure what-if must also be reviewed before deployment. No script modifies Render, production DNS, Supabase, or Nexora.
