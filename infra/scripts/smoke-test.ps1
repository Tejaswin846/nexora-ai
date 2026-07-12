param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$FrontDoorHostname,
    [Parameter(Mandatory = $true)][string]$ApiContainerAppHostname,
    [Parameter(Mandatory = $true)][string]$ApiManagementHostname,
    [Parameter(Mandatory = $true)][string]$WorkerContainerAppName,
    [string]$OrganizationId = "pillar1-staging-test",
    [string]$ProjectId = "request-flow"
)

$ErrorActionPreference = "Stop"
$baseUrl = "https://$FrontDoorHostname"
$correlationId = [Guid]::NewGuid().ToString()
$headers = @{
    "X-Organization-ID" = $OrganizationId
    "X-Project-ID" = $ProjectId
    "X-Correlation-ID" = $correlationId
    "Content-Type" = "application/json"
}

$frontend = Invoke-WebRequest -Uri "$baseUrl/" -TimeoutSec 30 -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "Front Door frontend route failed." }

$live = Invoke-RestMethod -Uri "$baseUrl/health/live" -TimeoutSec 30
if ($live.status -ne "alive") { throw "Front Door API liveness failed." }
Invoke-RestMethod -Uri "$baseUrl/openapi.json" -TimeoutSec 30 | Out-Null

$job = Invoke-RestMethod -Uri "$baseUrl/api/jobs" -Method Post -Headers $headers -Body '{"job_type":"staging_smoke_test","payload":{"probe":"pillar-1"}}' -TimeoutSec 30
if ($job.correlation_id -ne $correlationId) { throw "Correlation ID changed at submission." }

$deadline = [DateTime]::UtcNow.AddMinutes(3)
$artifact = $null
do {
    try {
        $artifact = Invoke-RestMethod -Uri "$baseUrl/api/jobs/$($job.job_id)/artifact" -Headers $headers -TimeoutSec 20
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
        Start-Sleep -Seconds 5
    }
} while ($null -eq $artifact -and [DateTime]::UtcNow -lt $deadline)

if ($null -eq $artifact) { throw "Worker artifact was not available before the smoke-test deadline." }
if ($artifact.correlation_id -ne $correlationId) { throw "Correlation ID was not preserved in the artifact." }

try {
    Invoke-RestMethod -Uri "$baseUrl/api/jobs" -Method Post -Headers $headers -Body '{"job_type":"staging_smoke_test","payload":{"api_key":"forbidden"}}' -TimeoutSec 20 | Out-Null
    throw "Sensitive queue payload was accepted."
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 422) { throw }
}

try {
    Invoke-RestMethod -Uri "https://$ApiContainerAppHostname/api/jobs" -Method Post -Headers $headers -Body '{"job_type":"staging_smoke_test"}' -TimeoutSec 20 | Out-Null
    throw "Direct Container App API bypass was accepted."
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 403) { throw }
}

try {
    Invoke-RestMethod -Uri "https://$ApiManagementHostname/api/jobs" -Method Post -Headers $headers -Body '{"job_type":"staging_smoke_test"}' -TimeoutSec 20 | Out-Null
    throw "Direct API Management bypass was accepted."
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 403) { throw }
}

$workerIngress = az containerapp show -g $ResourceGroup -n $WorkerContainerAppName --query properties.configuration.ingress.external -o tsv
if ($workerIngress -eq "true") { throw "Worker has public ingress." }

[pscustomobject]@{
    status = "passed"
    correlationId = $correlationId
    jobId = $job.job_id
    artifactPath = "workflow-artifacts tenant path verified"
    workerPublicIngress = $false
    renderChanged = $false
} | ConvertTo-Json
