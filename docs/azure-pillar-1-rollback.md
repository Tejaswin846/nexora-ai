# Azure Pillar 1 Rollback

Rollback preserves queues, Blob data, container images, and the Render fallback. Deletion is not a rollback mechanism.

## Exact command

```powershell
./infra/scripts/rollback-staging.ps1 `
  -ResourceGroup <staging-rg> `
  -ApiContainerAppName <api-app> `
  -PreviousHealthyRevision <revision> `
  -WorkerContainerAppName <worker-app> `
  -FrontDoorProfileName <front-door-profile> `
  -FrontDoorEndpointName <front-door-endpoint> `
  -DisableFrontDoorApiRoute
```

## Effects

- Routes 100% of API traffic to the specified healthy Container Apps revision.
- Sets worker replicas to zero, preserving queued messages.
- Optionally disables only the faulty Front Door API route.
- Leaves the frontend route, Service Bus queue, dead-letter queue, Blob Storage, ACR, identities, and logs intact.
- Does not modify Render or production DNS.

## Optional production APIM rollback

APIM is disabled in lean staging. If the production profile is approved later, redeploy the last known-good Bicep commit or restore the previous APIM backend named value and API policy through a reviewed infrastructure deployment. Do not place backend credentials on the command line or in the repository.

## Resume

After remediation, restore worker scaling from Bicep, re-enable the Front Door route, and run the full smoke test before accepting traffic.
