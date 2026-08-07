from __future__ import annotations

from typing import Any, Protocol


class BackgroundEventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class InMemoryBackgroundEventPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append({"event_type": event_type, "payload": payload})


class SafeBackgroundEventPublisher:
    def __init__(self, publisher: BackgroundEventPublisher | None = None) -> None:
        self.publisher = publisher or InMemoryBackgroundEventPublisher()
        self.failures: list[str] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            self.publisher.publish(event_type, payload)
        except Exception as error:
            self.failures.append(error.__class__.__name__)
