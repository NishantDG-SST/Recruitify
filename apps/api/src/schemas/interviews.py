from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RoundCreateRequest(BaseModel):
    round_name: str
    interviewer_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None

class RoundUpdateRequest(BaseModel):
    status: Optional[str] = None
    feedback: Optional[str] = None

class CandidateStatusUpdateRequest(BaseModel):
    status: str

class InterviewRoundResponse(BaseModel):
    id: str
    candidate_id: str
    round_name: str
    status: str
    feedback: Optional[str] = None
    interviewer_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    candidate_name: Optional[str] = None

class InterviewListResponse(BaseModel):
    interviews: list[InterviewRoundResponse]


class InterviewCandidate(BaseModel):
    candidate_id: str
    name: str
    role: str
    status: str
    fit_score: Optional[float] = None
    questions: list = []


class InterviewBoardResponse(BaseModel):
    candidates: list[InterviewCandidate]
