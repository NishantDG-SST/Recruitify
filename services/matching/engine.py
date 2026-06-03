import math
from typing import Dict, List

from services.matching.models import MatchEvidence, MatchInput, MatchResult


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


class MatchingEngine:
    def match(self, payload: MatchInput) -> MatchResult:
        scores: Dict[str, float] = {}
        evidence: Dict[str, List[MatchEvidence]] = {}

        # 1. Feature-level matching
        for key, candidate_score in payload.candidate_features.items():
            job_score = payload.job_features.get(key, 0.0)
            scores[key] = min(candidate_score, job_score)
            evidence[key] = []

        # 2. Semantic matching (if embeddings provided)
        if payload.candidate_embedding and payload.job_embedding:
            sim = cosine_similarity(payload.candidate_embedding, payload.job_embedding)
            # Clip between 0 and 1
            sim = max(0.0, min(1.0, sim))
            scores["semantic_similarity"] = sim
            evidence["semantic_similarity"] = [
                MatchEvidence(source="embedding_cosine", text=f"Cosine similarity: {sim:.3f}")
            ]

        return MatchResult(scores=scores, evidence=evidence)
