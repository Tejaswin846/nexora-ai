# Azure Pillar 1 WAF Findings

Status: configuration validated only; no WAF has been provisioned or traffic-tested.

Lean staging uses Front Door Standard with custom rules in Detection mode:

- API per-client-IP rate-limit rule, 300 requests/minute.
- Logging for unexpected `TRACE` and `TRACK` methods.

Front Door Standard supports routing, HTTPS redirect, caching, health probes, custom match rules, and custom rate-limit rules. Microsoft-managed WAF rule sets are supported only on Front Door Premium, so staging contains none. No claim is made that managed WAF behavior was tested.

After approved deployment, run dashboard, auth, upload, SDK, job, artifact, malformed request, bypass, and rate tests. Record rule ID, route, correlation ID, disposition, and false-positive status before changing Detection to Prevention.

Front Door Premium with Default Rule Set 2.1 and Bot Manager 1.1 remains the production upgrade option.

Sources: [Front Door WAF overview](https://learn.microsoft.com/azure/frontdoor/web-application-firewall), [Standard/Premium custom rate-limit sample](https://learn.microsoft.com/samples/azure/azure-quickstart-templates/front-door-standard-premium-rate-limit/).
