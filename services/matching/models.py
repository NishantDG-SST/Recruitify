from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MatchEvidence:
    source: str
    text: str


@dataclass(frozen=True)
class MatchInput:
    candidate_features: Dict[str, float]
    job_features: Dict[str, float]
    taxonomy_links: Dict[str, List[str]]
    candidate_embedding: List[float] | None = None
    job_embedding: List[float] | None = None


@dataclass(frozen=True)
class MatchResult:
    scores: Dict[str, float]
    evidence: Dict[str, List[MatchEvidence]]
