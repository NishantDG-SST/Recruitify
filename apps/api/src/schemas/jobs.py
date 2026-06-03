from typing import Optional

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    raw_text: Optional[str] = None
    title: Optional[str] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
