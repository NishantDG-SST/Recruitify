import uuid
from datetime import datetime
from typing import Dict, Optional

from services.workers.events import EventEnvelope, EventMetadata


def build_event(event_type: str, org_id: str, payload: Dict[str, object], correlation_id: Optional[str] = None) -> EventEnvelope:
    meta = EventMetadata(
        event_id=str(uuid.uuid4()),
        occurred_at=datetime.utcnow(),
        org_id=org_id,
        correlation_id=correlation_id,
    )
    return EventEnvelope(event_type=event_type, meta=meta, payload=payload)
