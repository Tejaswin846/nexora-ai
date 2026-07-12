# Azure Pillar 1 WAF Findings

Status: not executed because Front Door Premium has not been approved or provisioned.

The planned policy uses Microsoft Default Rule Set 2.1 and Bot Manager Rule Set 1.1 in Detection mode, plus a 300 requests/minute API rate-limit rule.

After deployment, run legitimate dashboard, auth, upload, SDK, job submission, artifact retrieval, and invalid-request tests. Record every managed-rule match with rule ID, route, correlation ID, disposition, and whether it is a true or false positive.

Do not create exclusions or switch to Prevention mode until the evidence shows legitimate requests are unaffected. No current WAF behavior is claimed as tested.
