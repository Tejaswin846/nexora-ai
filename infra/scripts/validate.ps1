param(
    [string]$Location = "centralindia"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$template = Join-Path $repoRoot "infra\bicep\main.bicep"
$parameters = Join-Path $repoRoot "infra\bicep\parameters\staging.bicepparam"

Push-Location $repoRoot
try {
    az bicep build --file $template --stdout | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Bicep compilation failed." }

    az deployment sub validate `
        --location $Location `
        --template-file $template `
        --parameters $parameters `
        --parameters deployWorkloads=false premiumFrontDoorCostApproved=false `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "Azure subscription-scope validation failed." }

    Write-Output "Pillar 1 Bicep validation passed."
} finally {
    Pop-Location
}
