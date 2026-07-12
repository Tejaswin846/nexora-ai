# Azure Pillar 1 Lean Staging Costs

Status: pre-deployment estimate only. No Software Azure resources exist.

Pricing checked at 2026-07-12 12:00 UTC in USD, before tax, negotiated discounts, support, and data transfer outside the assumptions below. Regional meters use Central India; Front Door uses global/India edge pricing; Static Web Apps uses East Asia. The authenticated subscription supports Central India for API Management and Container Apps. Retail prices came from the [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) and service pricing pages.

## Rejected architecture

| Resource | Rejected SKU | Fixed monthly estimate |
|---|---|---:|
| Front Door | Premium | $330.00 |
| API Management | Developer | $48.03 |
| Service Bus | Standard | $10.00 |
| Container Registry | Basic | $5.00 |
| **Rejected fixed baseline** | | **$393.03** |

The rejected low-traffic estimate was $393-$410/month. It remains available as code configuration but is not approved and will not be deployed.

## Lean staging estimate

| Resource | Staging SKU | Fixed/month | Usage meter and free allowance | Low traffic | Maximum expected | Idle / scale-to-zero | Delete to stop charge? |
|---|---|---:|---|---:|---:|---|---|
| Front Door | Standard | $35.00 | Requests and edge egress; custom WAF rules included | $0.54 | $8.23 | No scale-to-zero | Yes |
| API Management | Consumption, disabled | $0.00 | First 1M calls/month free when enabled, then usage | $0.00 | $0.00 | Consumption is request-based | No resource exists |
| Container Apps API + worker | Consumption, 0-2 each | $0.00 | 180k vCPU-s, 360k GiB-s, 2M requests free/subscription-month | $0.00 billed | $8.90 gross | Yes | No; scale to zero |
| Service Bus | Standard | $10.00 | Base includes the first 13M operations | $0.00 extra | $0.00 extra | No | Yes |
| Blob Storage | StorageV2 Cool, Standard_LRS | $0.00 | About $0.011/GB-month plus operations/retrieval | $0.16 | $2.10 | N/A | Data charges persist until deleted |
| Static Web Apps | Free | $0.00 | Free-plan quotas | $0.00 | $0.00 | N/A | No fixed charge |
| Container Registry | Basic | $5.07 | $0.1666/day; included storage then $0.10/GB-month | $0.00 extra | $0.00 extra | No | Yes |
| Log Analytics | PerGB2018, 30 days | $0.00 | First 5 GB/billing account may be free; then $3.22/GB in Central India | $0.00 | $16.10 | N/A | Retained/ingested data can charge |
| **Total** | | **$50.07 fixed** | | **$50.77/month** | **$85.40/month** | | |

Log ingestion is estimated separately at 1 GB/month low traffic ($0 if the billing-account allowance remains) and 5 GB/month maximum expected ($16.10 assuming the allowance is unavailable). The workspace uses 30-day retention, 25% successful-request log sampling, a 0.5 GB/day emergency cap, and an ingestion-growth alert. The cap can overshoot and is not a billing guarantee.

## Maximum-expected assumptions

The exact $85.40 estimate assumes 2 million Front Door requests, 25 GB edge egress, 300 aggregate active Container App replica-hours at 0.25 vCPU/0.5 GiB, 100 GB Cool LRS blobs, $1 of storage operations/retrieval, no more than 13 million Service Bus operations, and 5 GB billable logs.

This is an operating envelope, not a hard Azure spending cap. Two API and two worker replicas running continuously, cap overshoot, unusual egress, or high telemetry can exceed $100. Configure an Azure Budget alert at $75 and $90 before deployment; budget alerts notify but do not stop resources.

## Idle cost

With both apps at zero replicas and no traffic, the predictable baseline is **$50.07/month**, plus retained Blob/Log data. Front Door Standard, Service Bus Standard, and ACR Basic continue charging until deleted. Ordinary rollback does not delete persistent data.

## Pricing sources

- [Front Door pricing and billing](https://learn.microsoft.com/azure/frontdoor/billing)
- [API Management pricing](https://azure.microsoft.com/pricing/details/api-management/)
- [Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/)
- [Service Bus pricing](https://azure.microsoft.com/pricing/details/service-bus/)
- [Container Registry pricing](https://azure.microsoft.com/pricing/details/container-registry/)
- [Blob Storage pricing](https://azure.microsoft.com/pricing/details/storage/blobs/)
- [Azure Monitor pricing](https://azure.microsoft.com/pricing/details/monitor/)
