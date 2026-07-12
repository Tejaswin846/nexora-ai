# Azure Pillar 1 Lean Staging What-If

Executed: 2026-07-12 against the currently authenticated Azure subscription, Central India, using `staging.bicepparam`, `deployWorkloads=true`, and non-secret placeholder values for secure parameters.

Status: **Succeeded**. This operation was read-only and created nothing.

## Summary

| Change type | Count |
|---|---:|
| Create | 32 |
| Modify | 0 |
| Delete | 0 |
| Ignore | 0 |
| Unsupported evaluation | 6 |

The six unsupported evaluations are RBAC assignment names that depend on principal IDs of the two not-yet-created managed identities. Their roles and scopes are declared exactly below. This is an Azure what-if evaluation limitation, not an extra resource type.

## Exact creates

All resources are scoped to the new `rg-software-staging` group.

| Resource type | Name or child names |
|---|---|
| Resource group | `rg-software-staging` |
| Container Apps environment | `cae-software-staging-yydfdb` |
| Container Apps | `ca-software-api-staging-yydfdb`, `ca-software-worker-staging-yydfdb` |
| User-assigned identities | `id-software-api-staging-yydfdb`, `id-software-worker-staging-yydfdb` |
| Front Door profile | `afd-software-staging-yydfdb` |
| Front Door endpoint | `software-staging-yydfdb` |
| Front Door routes | `api-route`, `frontend-route` |
| Front Door origin groups | `api-origin-group`, `frontend-origin-group` |
| Front Door origins | `container-apps-api`, `static-web-app` |
| Front Door rule set/rule | `api-forwarding-headers`, `mark-approved-edge-path` |
| Front Door security policy | `waf-security-policy` |
| Front Door diagnostics | `front-door-diagnostics` |
| WAF policy | `waf-software-staging-yydfdb` |
| Container Registry | `acrsoftwarestgyydfdb` |
| Log Analytics | `log-software-staging-yydfdb` |
| Ingestion metric alert | `log-software-staging-yydfdb-ingestion-growth` |
| Service Bus namespace | `sb-software-staging-yydfdb` |
| Service Bus queue | `workflow-jobs` |
| Storage account | `stsoftwarestgyydfdb` |
| Blob service | `default` |
| Private Blob containers | `audit-exports`, `benchmark-exports`, `customer-reports`, `workflow-artifacts` |
| Storage lifecycle policy | `default` |
| Static Web App | `swa-software-staging-yydfdb` |

## RBAC assignments evaluated as unsupported

| Principal | Scope | Role |
|---|---|---|
| API identity | ACR | AcrPull |
| Worker identity | ACR | AcrPull |
| API identity | Service Bus namespace | Azure Service Bus Data Sender |
| Worker identity | Service Bus namespace | Azure Service Bus Data Receiver |
| API identity | Storage account | Storage Blob Data Contributor |
| Worker identity | Storage account | Storage Blob Data Contributor |

The GitHub deployer AcrPush assignment is conditional and absent because no deployment principal ID was supplied to the pre-approval what-if. It will appear only after the approved OIDC bootstrap provides that ID.

## Safety checks

- No existing resource is modified or deleted.
- Current Azure resource count remained 17 after what-if; no Software staging resource exists.
- No Nexora resource group, VM, disk, NIC, NSG, public IP, VNet, SSH key, or Network Watcher change appears.
- No Render, Supabase, production DNS, database, Key Vault, Event Hubs, Service Bus topic, Azure AI Foundry, Load Testing, AKS, Cosmos DB, or VM operation appears.
- Front Door is `Standard_AzureFrontDoor`; no Premium SKU or managed WAF rule set appears.
- APIM is absent because the Consumption policy compatibility fallback is active.
- Static Web Apps is Free, ACR is Basic, Service Bus is Standard, and Storage is Standard_LRS.
- API and worker are capped at two replicas and can scale to zero.
- No Owner role assignment appears.

## Command shape

The report was generated with `az deployment sub what-if --result-format ResourceIdOnly`. Secure parameters used literal placeholders, and subscription/tenant identifiers were removed from this report.
