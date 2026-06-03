from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class DecisionInput:
    candidate_id: str
    final_score: float
    passed_must_have: bool
    category_scores: Dict[str, float]


@dataclass(frozen=True)
class DecisionOutput:
    candidate_id: str
    rank: int
    decision: str
    triggers: List[str]
