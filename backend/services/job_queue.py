from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Protocol

from .message_schema import WorkflowJobMessage

try:
    from azure.identity import DefaultAzureCredential
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
except ImportError:  # pragma: no cover - exercised only in minimal local installs
    DefaultAzureCredential = None
    ServiceBusClient = None
    ServiceBusMessage = None


class JobQueue(Protocol):
    def enqueue(self, message: WorkflowJobMessage) -> None: ...


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.messages: list[WorkflowJobMessage] = []

    def enqueue(self, message: WorkflowJobMessage) -> None:
        self.messages.append(message)


class AzureServiceBusJobQueue:
    def __init__(self, namespace: str, queue_name: str) -> None:
        if DefaultAzureCredential is None or ServiceBusClient is None or ServiceBusMessage is None:
            raise RuntimeError("Azure Service Bus dependencies are not installed.")
        self.namespace = namespace
        self.queue_name = queue_name
        self.credential = DefaultAzureCredential()

    def enqueue(self, message: WorkflowJobMessage) -> None:
        payload = message.model_dump_json()
        service_bus_message = ServiceBusMessage(
            payload,
            content_type="application/json",
            message_id=str(message.job_id),
            correlation_id=str(message.correlation_id),
            application_properties={"schema_version": "1", "job_type": message.job_type},
        )
        with ServiceBusClient(self.namespace, credential=self.credential) as client:
            with client.get_queue_sender(self.queue_name) as sender:
                sender.send_messages(service_bus_message)


@lru_cache(maxsize=1)
def get_job_queue() -> JobQueue:
    namespace = os.getenv("AZURE_SERVICE_BUS_NAMESPACE", "").strip()
    queue_name = os.getenv("AZURE_SERVICE_BUS_QUEUE_NAME", "workflow-jobs").strip()
    environment = os.getenv("NEXORA_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower()
    if namespace:
        return AzureServiceBusJobQueue(namespace, queue_name)
    if environment in {"staging", "production"}:
        raise RuntimeError("AZURE_SERVICE_BUS_NAMESPACE is required in staging and production.")
    return InMemoryJobQueue()
