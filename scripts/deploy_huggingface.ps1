param(
  [string]$SpaceName = "nexora-ai",
  [string]$TokenPath = "$env:USERPROFILE\Desktop\hf_token.txt"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

if ($env:HF_TOKEN) {
  $Token = $env:HF_TOKEN.Trim()
} elseif (Test-Path -LiteralPath $TokenPath) {
  $Token = (Get-Content -LiteralPath $TokenPath -Raw).Trim()
} else {
  throw "Missing Hugging Face token. Set HF_TOKEN or save it to $TokenPath"
}

if (-not $Token) {
  throw "Hugging Face token is empty."
}

python -m pip install --user --upgrade huggingface_hub

$env:HF_TOKEN = $Token
$env:NEXORA_SPACE_NAME = $SpaceName
$env:NEXORA_REPO_ROOT = $RepoRoot

$DeployCode = @'
import os
from pathlib import Path

from huggingface_hub import HfApi

token = os.environ["HF_TOKEN"]
space_name = os.environ.get("NEXORA_SPACE_NAME", "nexora-ai").strip() or "nexora-ai"
repo_root = Path(os.environ["NEXORA_REPO_ROOT"]).resolve()

api = HfApi(token=token)
who = api.whoami(token=token)
username = who.get("name")
if not username:
    raise RuntimeError("Could not detect Hugging Face username from token.")

repo_id = f"{username}/{space_name}"
api.create_repo(
    repo_id=repo_id,
    repo_type="space",
    space_sdk="docker",
    private=False,
    exist_ok=True,
)

api.upload_folder(
    repo_id=repo_id,
    repo_type="space",
    folder_path=str(repo_root),
    path_in_repo=".",
    ignore_patterns=[
        ".git/*",
        ".git",
        ".vscode/*",
        "backend/venv/*",
        "backend/nexora_data/*",
        "backend/__pycache__/*",
        "__pycache__/*",
        "*.pyc",
        "*.log",
        "backend/uvicorn-*.log",
        "tmp-prod-data-test/*",
    ],
)

print(f"SPACE_REPO=https://huggingface.co/spaces/{repo_id}")
print(f"APP_URL=https://{username}-{space_name}.hf.space")
'@

$DeployCode | python -
