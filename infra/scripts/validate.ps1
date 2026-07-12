param(
    [string]$Location = "centralindia"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$template = Join-Path $repoRoot "infra\bicep\main.bicep"
$parameters = Join-Path $repoRoot "infra\bicep\parameters\staging.bicepparam"
$productionParameters = Join-Path $repoRoot "infra\bicep\parameters\production.bicepparam"

Push-Location $repoRoot
try {
    az bicep build --file $template --stdout | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Bicep compilation failed." }

    az bicep build-params --file $parameters --stdout | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Staging Bicep parameter compilation failed." }

    az bicep build-params --file $productionParameters --stdout | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Production Bicep parameter compilation failed." }

    az deployment sub validate `
        --location $Location `
        --template-file $template `
        --parameters $parameters `
        --parameters deployWorkloads=false `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "Azure subscription-scope validation failed." }

    Write-Output "Pillar 1 staging and production-profile Bicep validation passed."
} finally {
    Pop-Location
}
