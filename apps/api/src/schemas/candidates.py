from typing import Optional

from pydantic import BaseModel


class CandidateUploadResponse(BaseModel):
    batch_id: str


class CandidateDetailResponse(BaseModel):
    candidate_id: str
    profile: dict
    scores: dict
    evidence: dict
    questions: list
    status: Optional[str] = None
