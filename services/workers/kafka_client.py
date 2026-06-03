import json
from typing import Iterable, Optional

try:
    from kafka import KafkaConsumer, KafkaProducer
except ImportError as exc:  # pragma: no cover - runtime dependency check
    KafkaConsumer = None
    KafkaProducer = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from services.workers.events import EventEnvelope
from services.workers.schema_validation import SchemaValidator


class KafkaJsonProducer:
    def __init__(
        self,
        brokers: Iterable[str],
        validator: SchemaValidator,
        client_id: str = "recruitment-platform",
    ) -> None:
        if KafkaProducer is None:
            raise RuntimeError("kafka-python is required") from _IMPORT_ERROR
        self._validator = validator
        self._producer = KafkaProducer(
            bootstrap_servers=list(brokers),
            client_id=client_id,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    def publish(self, topic: str, event: EventEnvelope) -> None:
        self._validator.validate(event.event_type, event.payload)
        self._producer.send(topic, {
            "event_type": event.event_type,
            "meta": {
                "event_id": event.meta.event_id,
                "occurred_at": event.meta.occurred_at.isoformat(),
                "org_id": event.meta.org_id,
                "correlation_id": event.meta.correlation_id,
            },
            "payload": event.payload,
        })
        self._producer.flush()


class KafkaJsonConsumer:
    def __init__(
        self,
        brokers: Iterable[str],
        group_id: str,
        validator: SchemaValidator,
        client_id: str = "recruitment-platform",
        auto_offset_reset: str = "earliest",
    ) -> None:
        if KafkaConsumer is None:
            raise RuntimeError("kafka-python is required") from _IMPORT_ERROR
        self._validator = validator
        self._consumer = KafkaConsumer(
            bootstrap_servers=list(brokers),
            group_id=group_id,
            client_id=client_id,
            auto_offset_reset=auto_offset_reset,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def subscribe(self, topics: Iterable[str]) -> None:
        self._consumer.subscribe(list(topics))

    def poll(self) -> Iterable[EventEnvelope]:
        events = []
        for message in self._consumer.poll(timeout_ms=1000).values():
            for record in message:
                payload = record.value
                event_type = payload.get("event_type")
                meta = payload.get("meta", {})
                data = payload.get("payload", {})
                self._validator.validate(event_type, data)
                events.append(
                    EventEnvelope(
                        event_type=event_type,
                        meta=_meta_from_dict(meta),
                        payload=data,
                    )
                )
        return events


def _meta_from_dict(payload: dict) -> "EventMetadata":
    from services.workers.events import EventMetadata

    return EventMetadata(
        event_id=payload.get("event_id", ""),
        occurred_at=_parse_datetime(payload.get("occurred_at")),
        org_id=payload.get("org_id", ""),
        correlation_id=payload.get("correlation_id"),
    )


def _parse_datetime(value: Optional[str]) -> "datetime":
    from datetime import datetime

    if not value:
        return datetime.utcnow()
    return datetime.fromisoformat(value)
