param(
    [string]$ApiImage = "software-api:local",
    [string]$WorkerImage = "software-worker:local",
    [int]$Port = 8091
)

$ErrorActionPreference = "Stop"
$commitSha = (git rev-parse --short HEAD).Trim()
$buildTimestamp = [DateTime]::UtcNow.ToString("o")

docker build --file Dockerfile.api --build-arg "GIT_COMMIT_SHA=$commitSha" --build-arg "BUILD_TIMESTAMP=$buildTimestamp" --tag $ApiImage .
docker build --file Dockerfile.worker --build-arg "GIT_COMMIT_SHA=$commitSha" --build-arg "BUILD_TIMESTAMP=$buildTimestamp" --tag $WorkerImage .

$container = docker run --detach --rm --publish "${Port}:8000" --env NEXORA_ENV=development --env PORT=8000 $ApiImage
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $live = $null
    do {
        try {
            $live = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/live" -TimeoutSec 3
            if ($live.status -eq "alive") { break }
        } catch {
            Start-Sleep -Seconds 1
        }
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($null -eq $live -or $live.status -ne "alive") { throw "API container did not become live." }
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 5 | Out-Null
} finally {
    docker stop $container | Out-Null
}

docker run --rm --entrypoint python $WorkerImage -c "from backend.services.blob_storage import InMemoryBlobStorage; from worker.processor import WorkerProcessor; print('worker-import-ok')"
Write-Output "API and worker container verification passed."
