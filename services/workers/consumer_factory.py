from typing import List

from services.workers.consumer import EventConsumer, NoopConsumer
from services.workers.kafka_client import KafkaJsonConsumer
from services.workers.schema_definitions import SCHEMA_DEFINITIONS
from services.workers.schema_registry import SchemaRegistry
from services.workers.schema_validation import SchemaValidator


def build_consumer(brokers: List[str], group_id: str) -> EventConsumer:
    if not brokers:
        return NoopConsumer()
    registry = SchemaRegistry(SCHEMA_DEFINITIONS)
    validator = SchemaValidator(registry)
    return KafkaJsonConsumer(brokers=brokers, group_id=group_id, validator=validator)
