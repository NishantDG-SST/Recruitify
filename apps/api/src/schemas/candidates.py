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


class CandidateJobProfileResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    job_title: str
    status: str
    years_experience: int
    education_level: str
    certifications: list[str]
    career_trajectory: str
    domains: list[str]
    soft_skills: list[str]
    skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    fit_score: float
    fit_level: str
    fit_explanation: str
