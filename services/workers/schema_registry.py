from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class SchemaDefinition:
    event_type: str
    required_fields: List[str]


class SchemaRegistry:
    def __init__(self, definitions: Iterable[SchemaDefinition]) -> None:
        self._definitions: Dict[str, SchemaDefinition] = {
            definition.event_type: definition for definition in definitions
        }

    def required_fields_for(self, event_type: str) -> List[str]:
        if event_type not in self._definitions:
            raise ValueError(f"Unknown event type: {event_type}")
        return self._definitions[event_type].required_fields
