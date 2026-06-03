import math
from typing import List, Dict, Tuple

def compute_mrr(ranked_candidate_ids: List[str], relevant_candidate_ids: set[str]) -> float:
    """Compute Mean Reciprocal Rank for a single query (job)."""
    for index, candidate_id in enumerate(ranked_candidate_ids, start=1):
        if candidate_id in relevant_candidate_ids:
            return 1.0 / index
    return 0.0


def compute_dcg(ranked_ids: List[str], relevance_scores: Dict[str, float], k: int) -> float:
    """Compute Discounted Cumulative Gain at K."""
    dcg = 0.0
    for i in range(min(k, len(ranked_ids))):
        candidate_id = ranked_ids[i]
        rel = relevance_scores.get(candidate_id, 0.0)
        # DCG formula: rel / log2(rank + 1)
        dcg += rel / math.log2(i + 2)
    return dcg


def compute_ndcg(ranked_ids: List[str], relevance_scores: Dict[str, float], k: int) -> float:
    """Compute Normalized Discounted Cumulative Gain at K."""
    # Actual DCG
    actual_dcg = compute_dcg(ranked_ids, relevance_scores, k)
    
    # Ideal DCG (sort by relevance descending)
    ideal_ranked_ids = sorted(relevance_scores.keys(), key=lambda c: relevance_scores[c], reverse=True)
    ideal_dcg = compute_dcg(ideal_ranked_ids, relevance_scores, k)
    
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg
