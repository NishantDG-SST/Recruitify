from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApiMeta(BaseModel):
    request_id: Optional[str] = None
    timestamp: datetime
