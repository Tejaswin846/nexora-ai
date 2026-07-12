# Azure Pillar 1 Costs

Pricing checked on 2026-07-12 using current Microsoft retail pricing and Central India meters. Estimates are in USD before tax, discounts, support, and data transfer.

## Fixed monthly cost

| Resource | Staging selection | Estimate |
|---|---|---:|
| Azure Front Door | Premium, required for managed WAF | $330.00 |
| API Management | Developer, one unit, staging-only | $48.03 |
| Service Bus | Standard base | $10.00 |
| Container Registry | Basic | $5.00 |
| **Predictable fixed baseline** | | **about $393.03/month** |

## Usage-based cost

| Resource | Meter |
|---|---|
| Container Apps | Central India active vCPU about $0.000024/second; memory about $0.000003/GiB-second after free grants |
| Front Door Premium | India requests about $0.0168/10,000; edge transfer to India about $0.109/GB |
| Service Bus | First 13 million Standard operations included, then metered |
| Blob Storage | Cool LRS data about $0.011/GB-month, plus operations and retrieval |
| Log Analytics | First 5 GB/month per billing account free; Central India ingestion about $3.22/GB above allowance |
| APIM Developer | Fixed unit; no request overage expected for this staging tier |

## Free allowances

- Container Apps: 180,000 vCPU-seconds, 360,000 GiB-seconds, and two million requests per subscription each month.
- Static Web Apps Free: no fixed charge within Free-plan quotas.
- Azure Monitor: first 5 GB/month per billing account in the pay-as-you-go tier.

## Estimated staging cost

Low-traffic staging is expected to cost approximately **$393-$410/month**. Front Door Premium dominates the estimate. Log volume, data transfer, worker activity, and retained artifacts can increase it.

## Estimated low-traffic production cost

This staging architecture is not a production recommendation because APIM Developer has no SLA and Static Web Apps Free has no SLA. Replacing them with production tiers would materially increase the monthly cost and requires a separate review.

## Idle behavior

- API and worker can scale to zero and stop compute charges when idle.
- Front Door Premium, APIM Developer, Service Bus Standard, and ACR Basic continue charging while idle.
- Blob data, snapshots, Log Analytics ingestion/retention, and public data transfer remain usage-based.
- Stopping Container App replicas does not stop the fixed edge, gateway, bus, or registry charges.

## Approval

Provisioning is blocked until the approximately $393/month fixed baseline is explicitly approved. Front Door Standard would reduce cost to about $35/month but cannot satisfy the managed WAF rule requirement.
