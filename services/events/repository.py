import uuid
from dataclasses import dataclass
from typing import Dict

from apps.api.src.core.database import Database


@dataclass(frozen=True)
class EventRecord:
    event_id: str


import json

class EventRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def append(self, org_id: str, event_type: str, aggregate_type: str, aggregate_id: str, payload: Dict[str, object]) -> EventRecord:
        event_id = str(uuid.uuid4())

        if self._db.is_configured:
            self._db.execute(
                "INSERT INTO events (id, org_id, event_type, aggregate_type, aggregate_id, payload) VALUES (%s, %s, %s, %s, %s, %s)",
                [event_id, org_id, event_type, aggregate_type, aggregate_id, json.dumps(payload)],
            )

        return EventRecord(event_id=event_id)
