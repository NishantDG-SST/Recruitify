from pydantic import BaseModel


class MatchInput(BaseModel):
    candidate_id: str
    candidate_features: dict
    job_features: dict
    taxonomy_links: dict
    candidate_embedding: list[float] | None = None
    job_embedding: list[float] | None = None


class ScoreInput(BaseModel):
    match_scores: dict
    weights: dict
    must_have: list[str]


class DecisionInput(BaseModel):
    candidate_id: str
    final_score: float
    passed_must_have: bool
    category_scores: dict


class RankingCandidate(BaseModel):
    candidate_id: str
    candidate_name: str | None = None
    score: float
    rank: int
    explanation_text: str | None = None
    category_scores: dict | None = None
    status: str | None = None


class RankingResponse(BaseModel):
    run_id: str
    candidates: list[RankingCandidate]


class SimulateRankingRequest(BaseModel):
    candidates: list[MatchInput] | None = None
    weights: dict
    must_have: list[str] | None = None
    threshold: float | None = 40.0


class OverrideRequest(BaseModel):
    candidate_id: str
    old_rank: int
    new_rank: int
    reason: str
