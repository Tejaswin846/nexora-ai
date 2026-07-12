param(
    [Parameter(Mandatory = $true)]
    [switch]$ApproveLeanStagingCost,
    [string]$Location = "centralindia",
    [string]$DeploymentName = "software-pillar1-staging",
    [switch]$FoundationOnly
)

$ErrorActionPreference = "Stop"
if (-not $ApproveLeanStagingCost -or $env:AZURE_PILLAR1_LEAN_STAGING_APPROVED -ne "true") {
    throw "Deployment blocked. Supply -ApproveLeanStagingCost and set AZURE_PILLAR1_LEAN_STAGING_APPROVED=true only after explicit approval of the lean staging report."
}

$requiredEnvironment = @(
    "AZURE_DEPLOYER_PRINCIPAL_ID",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "NEXORA_AUTH_SECRET"
)
foreach ($name in $requiredEnvironment) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Required environment variable is missing: $name"
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$template = Join-Path $repoRoot "infra\bicep\main.bicep"
$parameters = Join-Path $repoRoot "infra\bicep\parameters\staging.bicepparam"
$commitSha = (git -C $repoRoot rev-parse HEAD).Trim()
$buildTimestamp = [DateTime]::UtcNow.ToString("o")
function Invoke-Deployment(
    [bool]$DeployWorkloads,
    [string]$FrontDoorHostname = "",
    [string]$ExpectedFrontDoorId = ""
) {
    az deployment sub create `
        --name $DeploymentName `
        --location $Location `
        --template-file $template `
        --parameters $parameters `
        --parameters `
            deployWorkloads=$($DeployWorkloads.ToString().ToLowerInvariant()) `
            gitCommitSha=$commitSha `
            apiImageTag=$commitSha `
            workerImageTag=$commitSha `
            buildTimestamp=$buildTimestamp `
            deployerPrincipalId=$env:AZURE_DEPLOYER_PRINCIPAL_ID `
            frontDoorHostname=$FrontDoorHostname `
            expectedFrontDoorId=$ExpectedFrontDoorId `
            supabaseUrl=$env:SUPABASE_URL `
            supabaseAnonKey=$env:SUPABASE_ANON_KEY `
            supabaseServiceRoleKey=$env:SUPABASE_SERVICE_ROLE_KEY `
            databaseUrl=$env:DATABASE_URL `
            upstashUrl=$env:UPSTASH_REDIS_REST_URL `
            upstashToken=$env:UPSTASH_REDIS_REST_TOKEN `
            authSecret=$env:NEXORA_AUTH_SECRET `
            posthogKey=$env:POSTHOG_PROJECT_API_KEY `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "Azure deployment failed." }
}

Push-Location $repoRoot
try {
    Invoke-Deployment -DeployWorkloads $false
    $outputs = az deployment sub show --name $DeploymentName --query properties.outputs -o json | ConvertFrom-Json
    $registryName = $outputs.registryName.value

    if ($FoundationOnly) {
        Write-Output "Foundation deployed. Workload and edge resources were not deployed."
        return
    }

    az acr login --name $registryName --only-show-errors | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "ACR login failed." }

    $registryServer = $outputs.registryLoginServer.value
    docker build --file Dockerfile.api --build-arg "GIT_COMMIT_SHA=$commitSha" --build-arg "BUILD_TIMESTAMP=$buildTimestamp" --tag "${registryServer}/api:${commitSha}" .
    docker build --file Dockerfile.worker --build-arg "GIT_COMMIT_SHA=$commitSha" --build-arg "BUILD_TIMESTAMP=$buildTimestamp" --tag "${registryServer}/worker:${commitSha}" .
    docker push "${registryServer}/api:${commitSha}"
    docker push "${registryServer}/worker:${commitSha}"

    Invoke-Deployment -DeployWorkloads $true
    $outputs = az deployment sub show --name $DeploymentName --query properties.outputs -o json | ConvertFrom-Json
    $frontDoorHostname = $outputs.frontDoorHostname.value
    $frontDoorId = $outputs.frontDoorId.value

    Invoke-Deployment -DeployWorkloads $true -FrontDoorHostname $frontDoorHostname -ExpectedFrontDoorId $frontDoorId
    $outputs = az deployment sub show --name $DeploymentName --query properties.outputs -o json | ConvertFrom-Json

    $resourceGroup = $outputs.resourceGroupName.value
    $staticWebAppName = (az staticwebapp list -g $resourceGroup --query "[0].name" -o tsv).Trim()
    $deploymentToken = (az staticwebapp secrets list -g $resourceGroup -n $staticWebAppName --query properties.apiKey -o tsv).Trim()
    try {
        $env:SWA_CLI_DEPLOYMENT_TOKEN = $deploymentToken
        npx.cmd --yes @azure/static-web-apps-cli@2.0.9 deploy ./frontend --deployment-token $env:SWA_CLI_DEPLOYMENT_TOKEN --env production
    } finally {
        Remove-Item Env:SWA_CLI_DEPLOYMENT_TOKEN -ErrorAction SilentlyContinue
        $deploymentToken = $null
    }

    Write-Output "Staging deployment completed. Run smoke-test.ps1 with the safe deployment outputs."
} finally {
    Pop-Location
}
