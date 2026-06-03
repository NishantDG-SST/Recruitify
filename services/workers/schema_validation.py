from typing import Dict

from services.workers.schema_registry import SchemaRegistry


class SchemaValidator:
    def __init__(self, registry: SchemaRegistry) -> None:
        self._registry = registry

    def validate(self, event_type: str, payload: Dict[str, object]) -> None:
        required_fields = self._registry.required_fields_for(event_type)
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Missing required fields for {event_type}: {missing}")
