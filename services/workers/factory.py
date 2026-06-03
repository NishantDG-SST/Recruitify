from typing import List

from services.workers.kafka_client import KafkaJsonProducer
from services.workers.producer import EventProducer, NoopProducer
from services.workers.schema_definitions import SCHEMA_DEFINITIONS
from services.workers.schema_registry import SchemaRegistry
from services.workers.schema_validation import SchemaValidator


def build_producer(brokers: List[str]) -> EventProducer:
    if not brokers:
        return NoopProducer()
    registry = SchemaRegistry(SCHEMA_DEFINITIONS)
    validator = SchemaValidator(registry)
    return KafkaJsonProducer(brokers=brokers, validator=validator)
