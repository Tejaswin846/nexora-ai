from __future__ import annotations

import asyncio
import json
import logging
import os
import signal

from pydantic import ValidationError

from backend.services.blob_storage import AzureBlobStorage
from backend.services.message_schema import WorkflowJobMessage
from worker.handlers.workflow import PermanentJobError, RetryableJobError
from worker.processor import WorkerProcessor

try:
    from azure.identity.aio import DefaultAzureCredential
    from azure.servicebus.aio import ServiceBusClient
except ImportError:  # pragma: no cover - startup validation handles this
    DefaultAzureCredential = None
    ServiceBusClient = None


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("software.worker")
stop_event = asyncio.Event()


def _request_shutdown() -> None:
    logger.info("worker_shutdown_requested")
    stop_event.set()


async def run_worker() -> None:
    namespace = os.environ["AZURE_SERVICE_BUS_NAMESPACE"]
    queue_name = os.getenv("AZURE_SERVICE_BUS_QUEUE_NAME", "workflow-jobs")
    storage_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
    if DefaultAzureCredential is None or ServiceBusClient is None:
        raise RuntimeError("Azure worker dependencies are not installed.")

    processor = WorkerProcessor(AzureBlobStorage(storage_url))
    credential = DefaultAzureCredential()
    client = ServiceBusClient(namespace, credential=credential)

    try:
        async with client:
            receiver = client.get_queue_receiver(queue_name=queue_name, max_wait_time=10)
            async with receiver:
                while not stop_event.is_set():
                    messages = await receiver.receive_messages(max_message_count=1, max_wait_time=5)
                    for service_bus_message in messages:
                        job: WorkflowJobMessage | None = None
                        try:
                            payload = b"".join(bytes(part) for part in service_bus_message.body).decode("utf-8")
                            job = WorkflowJobMessage.model_validate(json.loads(payload))
                            logger.info(
                                "job_received job_id=%s correlation_id=%s delivery_count=%s",
                                job.job_id,
                                job.correlation_id,
                                service_bus_message.delivery_count,
                            )
                            result = await asyncio.to_thread(processor.process, job)
                        except (ValidationError, json.JSONDecodeError, PermanentJobError) as error:
                            await receiver.dead_letter_message(
                                service_bus_message,
                                reason=type(error).__name__,
                                error_description=str(error)[:1024],
                            )
                            logger.warning(
                                "job_dead_lettered job_id=%s correlation_id=%s reason=%s",
                                getattr(job, "job_id", "unknown"),
                                getattr(job, "correlation_id", "unknown"),
                                type(error).__name__,
                            )
                        except RetryableJobError as error:
                            await receiver.abandon_message(service_bus_message)
                            logger.warning(
                                "job_abandoned job_id=%s correlation_id=%s reason=%s",
                                getattr(job, "job_id", "unknown"),
                                getattr(job, "correlation_id", "unknown"),
                                type(error).__name__,
                            )
                        except Exception as error:
                            if int(service_bus_message.delivery_count or 0) >= 5:
                                await receiver.dead_letter_message(
                                    service_bus_message,
                                    reason="UnhandledWorkerError",
                                    error_description=type(error).__name__,
                                )
                            else:
                                await receiver.abandon_message(service_bus_message)
                            logger.exception(
                                "job_processing_failed job_id=%s correlation_id=%s",
                                getattr(job, "job_id", "unknown"),
                                getattr(job, "correlation_id", "unknown"),
                            )
                        else:
                            await receiver.complete_message(service_bus_message)
                            logger.info(
                                "job_completed job_id=%s correlation_id=%s duplicate=%s artifact_path=%s",
                                job.job_id,
                                job.correlation_id,
                                result.duplicate,
                                result.artifact_path,
                            )
    finally:
        await credential.close()


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for signame in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signame, _request_shutdown)
        except NotImplementedError:  # Windows local verification
            signal.signal(signame, lambda *_args: loop.call_soon_threadsafe(_request_shutdown))
    loop.run_until_complete(run_worker())


if __name__ == "__main__":
    main()
