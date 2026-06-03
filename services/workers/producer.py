from typing import Protocol

from services.workers.events import EventEnvelope


class EventProducer(Protocol):
    def publish(self, topic: str, event: EventEnvelope) -> None:
        ...


class NoopProducer:
    def publish(self, topic: str, event: EventEnvelope) -> None:
        return None
