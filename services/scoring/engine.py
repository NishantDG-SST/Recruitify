from typing import Dict

from services.scoring.models import ScoreInput, ScoreOutput


class ScoringEngine:
    def score(self, payload: ScoreInput) -> ScoreOutput:
        category_scores: Dict[str, float] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for key, score in payload.match_scores.items():
            weight = payload.weights.get(key, 0.0)
            category_scores[key] = score * 100.0
            weighted_sum += score * weight
            total_weight += weight

        final_score = 0.0 if total_weight == 0.0 else weighted_sum / total_weight * 100.0
        
        feature_contributions: Dict[str, float] = {}
        if total_weight > 0.0:
            for key, score in payload.match_scores.items():
                weight = payload.weights.get(key, 0.0)
                feature_contributions[key] = (score * weight / total_weight) * 100.0

        passed_must_have = all(payload.match_scores.get(key, 0.0) > 0.0 for key in payload.must_have)

        return ScoreOutput(
            category_scores=category_scores,
            final_score=final_score,
            passed_must_have=passed_must_have,
            evidence=payload.evidence,
            feature_contributions=feature_contributions,
        )
