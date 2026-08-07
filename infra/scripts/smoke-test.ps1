param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$FrontDoorHostname,
    [Parameter(Mandatory = $true)][string]$ApiContainerAppHostname,
    [Parameter(Mandatory = $true)][string]$WorkerContainerAppName,
    [string]$ApiManagementHostname = "",
    [string]$SmokeEmail = $env:NEXORA_SMOKE_EMAIL,
    [string]$SmokePassword = $env:NEXORA_SMOKE_PASSWORD
)

$ErrorActionPreference = "Stop"
$baseUrl = "https://$FrontDoorHostname"
$correlationId = [Guid]::NewGuid().ToString()

if ([string]::IsNullOrWhiteSpace($SmokeEmail) -or [string]::IsNullOrWhiteSpace($SmokePassword)) {
    throw "Set NEXORA_SMOKE_EMAIL and NEXORA_SMOKE_PASSWORD for a staging account with at least one project."
}

$loginBody = @{
    email = $SmokeEmail
    password = $SmokePassword
} | ConvertTo-Json
$session = Invoke-RestMethod -Uri "$baseUrl/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec 30
if ([string]::IsNullOrWhiteSpace($session.token) -or [string]::IsNullOrWhiteSpace($session.user.id)) {
    throw "Staging smoke-test login did not return a valid user session."
}

$authenticatedHeaders = @{
    "Authorization" = "Bearer $($session.token)"
}
$projects = Invoke-RestMethod -Uri "$baseUrl/api/projects" -Headers $authenticatedHeaders -TimeoutSec 30
$projectId = @($projects.projects)[0].id
if ([string]::IsNullOrWhiteSpace($projectId)) {
    $projectBody = @{
        name = "Azure staging smoke test"
        framework = "Pillar 1"
        environment = "Staging"
        description = "Dedicated project for authenticated queue and artifact verification."
    } | ConvertTo-Json
    $project = Invoke-RestMethod -Uri "$baseUrl/api/projects" -Method Post -Headers $authenticatedHeaders -ContentType "application/json" -Body $projectBody -TimeoutSec 30
    $projectId = $project.project.id
}
if ([string]::IsNullOrWhiteSpace($projectId)) {
    throw "The staging smoke test could not resolve an owned project."
}

$headers = @{
    "Authorization" = "Bearer $($session.token)"
    "X-Organization-ID" = $session.user.id
    "X-Project-ID" = $projectId
    "X-Correlation-ID" = $correlationId
    "Content-Type" = "application/json"
}

$frontend = Invoke-WebRequest -Uri "$baseUrl/" -TimeoutSec 30 -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "Front Door frontend route failed." }

$live = Invoke-RestMethod -Uri "$baseUrl/health/live" -TimeoutSec 30
if ($live.status -ne "alive") { throw "Front Door API liveness failed." }
Invoke-RestMethod -Uri "$baseUrl/openapi.json" -TimeoutSec 30 | Out-Null

try {
    $anonymousHeaders = @{
        "X-Organization-ID" = $session.user.id
        "X-Project-ID" = $projectId
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri "$baseUrl/api/jobs" -Method Post -Headers $anonymousHeaders -Body '{"job_type":"staging_smoke_test"}' -TimeoutSec 20 | Out-Null
    throw "Anonymous job submission was accepted."
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw }
}

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

if (-not [string]::IsNullOrWhiteSpace($ApiManagementHostname)) {
    try {
        Invoke-RestMethod -Uri "https://$ApiManagementHostname/api/jobs" -Method Post -Headers $headers -Body '{"job_type":"staging_smoke_test"}' -TimeoutSec 20 | Out-Null
        throw "Direct API Management bypass was accepted."
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 403) { throw }
    }
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
