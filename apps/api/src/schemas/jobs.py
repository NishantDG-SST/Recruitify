from typing import Optional

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    raw_text: Optional[str] = None
    title: Optional[str] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobDetailResponse(BaseModel):
    id: str
    title: str
    raw_text: str
    parsed_json: Optional[dict] = None
    created_at: str
