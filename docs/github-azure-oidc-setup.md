# GitHub Azure OIDC Setup

Run these commands only after lean staging is explicitly approved. They create no password or permanent client secret. Replace the organization and repository placeholders locally; never commit IDs produced by the commands.

## 1. Select the authenticated subscription and staging resource group

```powershell
$subscriptionId = az account show --query id -o tsv
$tenantId = az account show --query tenantId -o tsv
$resourceGroup = "rg-software-staging"
$location = "centralindia"

az group create --name $resourceGroup --location $location `
  --tags project=software environment=staging pillar=1 managedBy=bicep costProfile=lean `
  --only-show-errors --output none
```

Creating the empty resource group is part of the approved bootstrap. It does not deploy Software workloads.

## 2. Create the deployment identity and federated credential

```powershell
$githubOrganization = "<github-organization>"
$githubRepository = "<github-repository>"
$displayName = "software-pillar1-staging-github"

$app = az ad app create --display-name $displayName -o json | ConvertFrom-Json
$servicePrincipal = az ad sp create --id $app.appId -o json | ConvertFrom-Json

$federatedCredential = @{
  name = "github-staging"
  issuer = "https://token.actions.githubusercontent.com"
  subject = "repo:$githubOrganization/${githubRepository}:environment:staging"
  description = "Software Pillar 1 protected staging environment"
  audiences = @("api://AzureADTokenExchange")
} | ConvertTo-Json -Compress

az ad app federated-credential create --id $app.id `
  --parameters $federatedCredential --only-show-errors --output none
```

The subject is restricted to the GitHub Environment named `staging`; branch-only tokens cannot use it.

## 3. Assign least-privilege deployment permissions

The deployment creates runtime RBAC assignments, so the identity needs resource management and RBAC management only inside the staging resource group. The current subscription-scope wrapper also needs narrowly scoped deployment invocation permission; it must not receive Owner.

```powershell
$resourceGroupId = az group show --name $resourceGroup --query id -o tsv
$subscriptionScope = "/subscriptions/$subscriptionId"

az role assignment create --assignee-object-id $servicePrincipal.id `
  --assignee-principal-type ServicePrincipal --role Contributor `
  --scope $resourceGroupId --only-show-errors --output none

az role assignment create --assignee-object-id $servicePrincipal.id `
  --assignee-principal-type ServicePrincipal --role "Role Based Access Control Administrator" `
  --scope $resourceGroupId --only-show-errors --output none

$roleDefinition = @{
  Name = "Software Staging Deployment Invoker"
  IsCustom = $true
  Description = "Invoke subscription deployments targeting the pre-created Software staging resource group."
  Actions = @(
    "Microsoft.Resources/deployments/*",
    "Microsoft.Resources/subscriptions/resourceGroups/read",
    "Microsoft.Resources/subscriptions/resourceGroups/write"
  )
  NotActions = @()
  AssignableScopes = @($subscriptionScope)
} | ConvertTo-Json -Depth 10 -Compress

az role definition create --role-definition $roleDefinition --only-show-errors --output none
az role assignment create --assignee-object-id $servicePrincipal.id `
  --assignee-principal-type ServicePrincipal --role "Software Staging Deployment Invoker" `
  --scope $subscriptionScope --only-show-errors --output none
```

The custom role cannot manage billing, secrets, VMs, Nexora resources, or production DNS. Its resource-group write permission is only needed because the checked-in subscription template declares the already named staging group; review the what-if before every deployment.

## 4. Configure GitHub variables and secrets

Set these repository or `staging` environment **variables**:

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | `$app.appId` |
| `AZURE_TENANT_ID` | `$tenantId` |
| `AZURE_SUBSCRIPTION_ID` | `$subscriptionId` |
| `AZURE_DEPLOYER_PRINCIPAL_ID` | `$servicePrincipal.id` |
| `AZURE_PILLAR1_LEAN_STAGING_APPROVED` | Leave unset until explicit approval; then `true` |

Set genuine application values as `staging` environment **secrets**:

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `NEXORA_AUTH_SECRET`, and optional `POSTHOG_PROJECT_API_KEY`.

No `AZURE_CLIENT_SECRET` is used.

## 5. Protect and verify the environment

In GitHub: Settings -> Environments -> `staging`:

1. Add required reviewers who can approve Azure spend.
2. Restrict deployment branches to `infra/azure-pillar-1`.
3. Prevent self-review where the repository plan supports it.
4. Keep the lean-staging approval variable unset until the final report is accepted.

Verify OIDC with a manually dispatched, non-deploy diagnostic job or locally inspect the identity:

```powershell
az ad app federated-credential list --id $app.id `
  --query "[].{name:name,subject:subject,issuer:issuer}" -o table
az role assignment list --assignee-object-id $servicePrincipal.id `
  --query "[].{role:roleDefinitionName,scope:scope}" -o table
```

The workflow sets `AZURE_CORE_OUTPUT=none` to reduce identifier leakage in logs. Microsoft recommends OIDC for `azure/login`; IDs are identifiers, not credentials, but they are still kept out of committed files.

## Sources

- [Azure Login OIDC guidance](https://github.com/Azure/login)
- [GitHub OIDC with Azure](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Azure RBAC scope](https://learn.microsoft.com/azure/role-based-access-control/scope-overview)
