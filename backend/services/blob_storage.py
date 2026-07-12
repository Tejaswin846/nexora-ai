from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient, ContentSettings
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:  # pragma: no cover - exercised only in minimal local installs
    DefaultAzureCredential = None
    BlobServiceClient = None
    ContentSettings = None
    ResourceNotFoundError = Exception


TENANT_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")


def tenant_blob_path(organization_id: str, project_id: str, category: str, filename: str) -> str:
    values = (organization_id, project_id, category)
    if any(not TENANT_SEGMENT.fullmatch(value) for value in values):
        raise ValueError("invalid tenant blob path segment")
    if not filename or filename != os.path.basename(filename) or "/" in filename or "\\" in filename:
        raise ValueError("invalid blob filename")
    return f"organizations/{organization_id}/projects/{project_id}/{category}/{filename}"


class BlobStorage(Protocol):
    def upload_json(self, container: str, blob_name: str, value: dict[str, Any], *, overwrite: bool = False) -> None: ...
    def download_json(self, container: str, blob_name: str) -> dict[str, Any]: ...
    def exists(self, container: str, blob_name: str) -> bool: ...


class InMemoryBlobStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}

    def upload_json(self, container: str, blob_name: str, value: dict[str, Any], *, overwrite: bool = False) -> None:
        key = (container, blob_name)
        if key in self.objects and not overwrite:
            raise FileExistsError(blob_name)
        self.objects[key] = json.loads(json.dumps(value))

    def download_json(self, container: str, blob_name: str) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(self.objects[(container, blob_name)]))
        except KeyError as error:
            raise FileNotFoundError(blob_name) from error

    def exists(self, container: str, blob_name: str) -> bool:
        return (container, blob_name) in self.objects


class AzureBlobStorage:
    def __init__(self, account_url: str) -> None:
        if DefaultAzureCredential is None or BlobServiceClient is None:
            raise RuntimeError("Azure Blob Storage dependencies are not installed.")
        self.client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())

    def upload_json(self, container: str, blob_name: str, value: dict[str, Any], *, overwrite: bool = False) -> None:
        self.client.get_blob_client(container, blob_name).upload_blob(
            json.dumps(value, separators=(",", ":"), default=str),
            overwrite=overwrite,
            content_settings=ContentSettings(content_type="application/json"),
        )

    def download_json(self, container: str, blob_name: str) -> dict[str, Any]:
        try:
            data = self.client.get_blob_client(container, blob_name).download_blob().readall()
        except ResourceNotFoundError as error:
            raise FileNotFoundError(blob_name) from error
        return json.loads(data)

    def exists(self, container: str, blob_name: str) -> bool:
        return self.client.get_blob_client(container, blob_name).exists()
