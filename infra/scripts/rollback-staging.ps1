param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$ApiContainerAppName,
    [Parameter(Mandatory = $true)][string]$PreviousHealthyRevision,
    [Parameter(Mandatory = $true)][string]$WorkerContainerAppName,
    [Parameter(Mandatory = $true)][string]$FrontDoorProfileName,
    [Parameter(Mandatory = $true)][string]$FrontDoorEndpointName,
    [switch]$DisableFrontDoorApiRoute
)

$ErrorActionPreference = "Stop"

az containerapp revision set-mode -g $ResourceGroup -n $ApiContainerAppName --mode multiple --only-show-errors
az containerapp ingress traffic set -g $ResourceGroup -n $ApiContainerAppName --revision-weight "${PreviousHealthyRevision}=100" --only-show-errors
az containerapp update -g $ResourceGroup -n $WorkerContainerAppName --min-replicas 0 --max-replicas 0 --only-show-errors

if ($DisableFrontDoorApiRoute) {
    az afd route update `
        -g $ResourceGroup `
        --profile-name $FrontDoorProfileName `
        --endpoint-name $FrontDoorEndpointName `
        --route-name api-route `
        --enabled-state Disabled `
        --only-show-errors
}

Write-Output "Rollback applied. Queue messages and Blob data were preserved; Render was not changed."
