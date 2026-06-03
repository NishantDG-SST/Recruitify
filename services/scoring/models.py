from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ScoreEvidence:
    source: str
    text: str


@dataclass(frozen=True)
class ScoreInput:
    match_scores: Dict[str, float]
    weights: Dict[str, float]
    must_have: List[str]
    evidence: Dict[str, List[ScoreEvidence]]


@dataclass(frozen=True)
class ScoreOutput:
    category_scores: Dict[str, float]
    final_score: float
    passed_must_have: bool
    evidence: Dict[str, List[ScoreEvidence]]
    feature_contributions: Dict[str, float]
