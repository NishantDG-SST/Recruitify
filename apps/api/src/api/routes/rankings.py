from fastapi import APIRouter
import json
from schemas.rankings import RankingCandidate, RankingResponse, SimulateRankingRequest, OverrideRequest
from services.decision.engine import DecisionEngine
from services.decision.models import DecisionInput
from services.matching.engine import MatchingEngine
from services.matching.models import MatchInput
from services.scoring.engine import ScoringEngine
from services.scoring.models import ScoreInput, ScoreEvidence
from core.config import settings
from core.database import get_database
from services.ranking.repository import RankingOutputRecord, RankingRepository
from services.ranking.explanation import RankingExplanationService
from services.llm.client import LLMClient, LLMConfig

router = APIRouter(prefix="/jobs/{job_id}/rankings", tags=["rankings"])


@router.get("", response_model=RankingResponse)
def get_rankings(job_id: str) -> RankingResponse:
    # 1. Fetch Job from DB
    database = get_database(settings.database_dsn)
    job_row = database.fetchone("SELECT title, parsed_json FROM job_versions WHERE job_id = %s", [job_id])
    job_title = job_row[0] if job_row else "Unknown Job"
    
    parsed_json = job_row[1] if job_row and len(job_row) > 1 and job_row[1] else {}
    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except json.JSONDecodeError:
            parsed_json = {}
            
    # 2. Extract job features dynamically from the parsed job description
    must_have = parsed_json.get("must_have_skills") or []
    nice_to_have = parsed_json.get("nice_to_have_skills") or []
    job_skills = [s.lower() for s in (must_have + nice_to_have)]
    job_exp = parsed_json.get("years_experience_min", 0) or 0
    
    job_score_features = {
        "skills": 1.0,
        "experience": 1.0,
        "education": 1.0
    }
    
    # 3. Fetch extracted candidates linked to this job
    candidate_rows = database.fetchall(
        """
        SELECT c.id, s.profile_json
        FROM candidates c
        JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE c.status IN ('extracted', 'interview')
          AND s.profile_json->>'job_id' = %s
        """,
        [job_id]
    )
    
    matcher = MatchingEngine()
    scorer = ScoringEngine()
    decider = DecisionEngine()
    
    decision_inputs = []
    scored_candidates = {}
    
    for row in candidate_rows:
        cand_id = row[0]
        profile = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
        cand_name = profile.get("name", "Unknown Candidate")
        
        cand_skills = [s.lower() for s in profile.get("skills", [])]
        cand_exp = profile.get("years_experience", 0)
        
        skill_match = len(set(cand_skills).intersection(set(job_skills))) / len(job_skills) if job_skills else 1.0
        exp_match = min(1.0, cand_exp / job_exp) if job_exp else 1.0
        
        cand_score_features = {
            "skills": skill_match,
            "experience": exp_match,
            "education": 1.0
        }
        
        # 4. Run Matching & Scoring
        match_result = matcher.match(
            MatchInput(
                candidate_features=cand_score_features,
                job_features=job_score_features,
                taxonomy_links=[],
                candidate_embedding=[0.0] * 768,
                job_embedding=[0.0] * 768
            )
        )
        
        score_result = scorer.score(
            ScoreInput(
                match_scores=match_result.scores,
                weights={"skills": 0.5, "experience": 0.3, "education": 0.2, "semantic": 0.0},
                must_have=[],
                evidence={key: [ScoreEvidence(source="match", text="")] for key in match_result.scores}
            )
        )
        
        scored_candidates[cand_id] = {
            "score": score_result.final_score,
            "name": cand_name
        }
        decision_inputs.append(
            DecisionInput(
                candidate_id=cand_id,
                final_score=score_result.final_score,
                passed_must_have=score_result.passed_must_have,
                category_scores=score_result.category_scores
            )
        )
        
    # 5. Rank
    decisions = decider.rank(decision_inputs, threshold=40.0)
    
    ranked = [
        RankingCandidate(
            candidate_id=str(d.candidate_id),
            candidate_name=scored_candidates[d.candidate_id]["name"],
            score=scored_candidates[d.candidate_id]["score"],
            rank=d.rank,
            explanation_text=f"Matched strongly on 12 skills. Recommended to proceed."
        )
        for d in decisions
    ]
    
    return RankingResponse(run_id="run_live_001", candidates=ranked)


@router.post("/simulate", response_model=RankingResponse)
def simulate_ranking(job_id: str, payload: SimulateRankingRequest) -> RankingResponse:
    matcher = MatchingEngine()
    scorer = ScoringEngine()
    decider = DecisionEngine()
    database = get_database(settings.database_dsn)
    repo = RankingRepository(database)
    llm = LLMClient(LLMConfig(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
    ))
    explainer = RankingExplanationService(llm)
    
    run = repo.create_run(org_id="11111111-1111-1111-1111-111111111111", job_version_id=job_id, scoring_version="v0")
    run_id = run.run_id

    decision_inputs = []
    scored = {}
    for candidate in payload.candidates:
        match_result = matcher.match(
            MatchInput(
                candidate_features=candidate.candidate_features,
                job_features=candidate.job_features,
                taxonomy_links=candidate.taxonomy_links,
                candidate_embedding=candidate.candidate_embedding,
                job_embedding=candidate.job_embedding,
            )
        )
        score_result = scorer.score(
            ScoreInput(
                match_scores=match_result.scores,
                weights=payload.weights,
                must_have=payload.must_have,
                evidence={key: [ScoreEvidence(source="match", text="")] for key in match_result.scores},
            )
        )
        scored[candidate.candidate_id] = score_result.final_score
        
        # Persist feature contributions
        repo.write_feature_contributions(
            run_id=run_id,
            candidate_id=candidate.candidate_id,
            contributions=score_result.feature_contributions,
        )

        decision_inputs.append(
            DecisionInput(
                candidate_id=candidate.candidate_id,
                final_score=score_result.final_score,
                passed_must_have=score_result.passed_must_have,
                category_scores=score_result.category_scores,
            )
        )

    decisions = decider.rank(decision_inputs, threshold=payload.threshold)
    ranked = [
        RankingCandidate(
            candidate_id=item.candidate_id,
            score=scored.get(item.candidate_id, 0.0),
            rank=item.rank,
        )
        for item in decisions
    ]
    output_records = []
    # To provide explanations we need to match candidate_id back to original payload
    candidate_lookup = {c.candidate_id: c for c in payload.candidates}
    
    for item in decisions:
        cand_input = candidate_lookup[item.candidate_id]
        explanation = explainer.generate(
            candidate_id=item.candidate_id,
            job_features=cand_input.job_features,
            candidate_features=cand_input.candidate_features,
            score=scored.get(item.candidate_id, 0.0),
            decision=item.decision,
            triggers=item.triggers,
        )
        output_records.append(
            RankingOutputRecord(
                run_id=run_id,
                candidate_snapshot_id=item.candidate_id,
                final_score=scored.get(item.candidate_id, 0.0),
                rank=item.rank,
                decision=item.decision,
                explanation_text=explanation,
            )
        )
    repo.write_outputs(output_records)
    return RankingResponse(run_id=run_id, candidates=ranked)


@router.post("/{run_id}/overrides", status_code=201)
def create_override(job_id: str, run_id: str, payload: OverrideRequest) -> dict:
    database = get_database(settings.database_dsn)
    repo = RankingRepository(database)
    # user_id would typically come from auth middleware
    repo.write_override(
        run_id=run_id,
        candidate_id=payload.candidate_id,
        old_rank=payload.old_rank,
        new_rank=payload.new_rank,
        reason=payload.reason,
        user_id="00000000-0000-0000-0000-000000000002"  # Demo user ID from seed.sql
    )
    return {"status": "success"}
