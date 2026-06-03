from dataclasses import dataclass
from typing import Dict, List, Set
from services.evaluation.metrics import compute_mrr, compute_ndcg

@dataclass
class GroundTruth:
    job_id: str
    relevance_scores: Dict[str, float]  # candidate_id -> relevance (0.0 to 1.0)
    
    @property
    def relevant_candidates(self) -> Set[str]:
        # Consider candidates with relevance > 0.5 as "relevant" for MRR
        return {c for c, score in self.relevance_scores.items() if score > 0.5}


@dataclass
class EvaluationReport:
    model_version: str
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float
    job_count: int


class OfflineEvaluator:
    """Evaluates ranking models against a static ground-truth dataset."""

    def __init__(self, ground_truths: List[GroundTruth]):
        self.ground_truths = {gt.job_id: gt for gt in ground_truths}

    def evaluate_run(self, model_version: str, ranking_results: Dict[str, List[str]]) -> EvaluationReport:
        """
        Evaluate a model's rankings.
        ranking_results maps job_id -> list of candidate_ids (in ranked order)
        """
        total_mrr = 0.0
        total_ndcg_5 = 0.0
        total_ndcg_10 = 0.0
        evaluated_jobs = 0
        
        for job_id, ranked_ids in ranking_results.items():
            if job_id not in self.ground_truths:
                continue
                
            gt = self.ground_truths[job_id]
            
            mrr = compute_mrr(ranked_ids, gt.relevant_candidates)
            ndcg_5 = compute_ndcg(ranked_ids, gt.relevance_scores, 5)
            ndcg_10 = compute_ndcg(ranked_ids, gt.relevance_scores, 10)
            
            total_mrr += mrr
            total_ndcg_5 += ndcg_5
            total_ndcg_10 += ndcg_10
            evaluated_jobs += 1
            
        if evaluated_jobs == 0:
            return EvaluationReport(model_version, 0.0, 0.0, 0.0, 0)
            
        return EvaluationReport(
            model_version=model_version,
            mrr=total_mrr / evaluated_jobs,
            ndcg_at_5=total_ndcg_5 / evaluated_jobs,
            ndcg_at_10=total_ndcg_10 / evaluated_jobs,
            job_count=evaluated_jobs
        )
