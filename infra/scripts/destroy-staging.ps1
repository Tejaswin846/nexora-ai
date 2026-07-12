param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [switch]$BreakGlass,
    [string]$Confirmation
)

$expected = "DELETE-STAGING-ONLY-$ResourceGroup"
if (-not $BreakGlass -or $Confirmation -cne $expected) {
    Write-Output "Destruction is disabled by default. No resource was deleted."
    Write-Output "Break-glass confirmation would have to match: $expected"
    exit 2
}

throw "Automated deletion remains intentionally disabled for Pillar 1. Review retained queues, blobs, revisions, and rollback requirements before implementing a deletion procedure."
