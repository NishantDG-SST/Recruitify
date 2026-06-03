from typing import Callable, Iterable, Protocol

from services.workers.events import EventEnvelope


EventHandler = Callable[[EventEnvelope], None]


class EventConsumer(Protocol):
    def subscribe(self, topics: Iterable[str]) -> None:
        ...

    def poll(self) -> Iterable[EventEnvelope]:
        ...


class NoopConsumer:
    def subscribe(self, topics: Iterable[str]) -> None:
        return None

    def poll(self) -> Iterable[EventEnvelope]:
        return []
