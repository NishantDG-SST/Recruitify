from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EventMetadata:
    event_id: str
    occurred_at: datetime
    org_id: str
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    meta: EventMetadata
    payload: Dict[str, Any]
