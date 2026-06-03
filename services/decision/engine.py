from typing import Iterable, List

from services.decision.models import DecisionInput, DecisionOutput


class DecisionEngine:
    def rank(self, candidates: Iterable[DecisionInput], threshold: float) -> List[DecisionOutput]:
        ordered = sorted(candidates, key=lambda item: item.final_score, reverse=True)
        outputs: List[DecisionOutput] = []

        for index, candidate in enumerate(ordered, start=1):
            decision = "shortlist" if candidate.final_score >= threshold and candidate.passed_must_have else "reject"
            triggers = [] if candidate.passed_must_have else ["must_have_failed"]
            outputs.append(
                DecisionOutput(
                    candidate_id=candidate.candidate_id,
                    rank=index,
                    decision=decision,
                    triggers=triggers,
                )
            )

        return outputs
