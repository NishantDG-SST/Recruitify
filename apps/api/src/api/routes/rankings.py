from fastapi import APIRouter, Depends, HTTPException
import json
import os
import re
from schemas.rankings import RankingCandidate, RankingResponse, SimulateRankingRequest, OverrideRequest
from services.decision.engine import DecisionEngine
from services.decision.models import DecisionInput
from services.matching.engine import MatchingEngine
from services.matching.models import MatchInput
from services.scoring.engine import ScoringEngine
from services.scoring.models import ScoreInput, ScoreEvidence
from core.config import settings
from core.database import get_database
from core.auth import SecurityContext, get_security_context
from services.ranking.repository import RankingOutputRecord, RankingRepository
from services.ranking.explanation import RankingExplanationService
from services.llm.client import LLMClient, LLMConfig
from services.scoring.llm_judge import score_fit, reconcile_requirements, _requirement_satisfied

router = APIRouter(prefix="/jobs/{job_id}/rankings", tags=["rankings"])

# ---------------------------------------------------------------------------
# Scoring configuration (sourced from the ranking_models table; the constants
# below are only the seed/last-resort defaults if no model row exists).
# ---------------------------------------------------------------------------

DEFAULT_RANKING_CONFIG = {
    "weights": {"skills": 0.4, "experience": 0.15, "education": 0.1, "semantic_similarity": 0.35},
    "skills_gate": 0.15,        # below this normalized skills score, experience/education are zeroed
    "shortlist_threshold": 40.0,
}


def load_ranking_config(database) -> dict:
    """Load scoring weights/thresholds from the active ranking model, with safe defaults."""
    row = None
    try:
        row = database.fetchone("SELECT metadata_json FROM ranking_models ORDER BY created_at DESC LIMIT 1", [])
    except Exception:
        row = None
    meta = row[0] if row and row[0] else None
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = None
    if not isinstance(meta, dict):
        meta = {}
    return {
        "weights": meta.get("weights") or DEFAULT_RANKING_CONFIG["weights"],
        "skills_gate": float(meta.get("skills_gate", DEFAULT_RANKING_CONFIG["skills_gate"])),
        "shortlist_threshold": float(meta.get("shortlist_threshold", DEFAULT_RANKING_CONFIG["shortlist_threshold"])),
    }


def get_fit(database, llm, candidate_id, profile: dict, job_parsed: dict, job_version_id, force: bool = False) -> dict:
    """Return the LLM-judged fit for a candidate against a job, cached per job_version_id.

    Cache lives in candidate_snapshots.profile_json.llm_fit, keyed by job_version_id so a
    snapshot can be scored against multiple jobs without overwrite. generate_rankings passes
    force=True; read paths (display/simulate/modal) reuse the cache → no LLM calls, deterministic.
    """
    key = str(job_version_id)
    llm_fit = profile.get("llm_fit") or {}
    if not force and key in llm_fit:
        return llm_fit[key]

    fit = score_fit(job_parsed, profile, llm)
    llm_fit[key] = fit
    profile["llm_fit"] = llm_fit  # keep the in-memory profile consistent

    if candidate_id and database is not None and database.is_configured:
        # Write the full merged map; the shallow `||` merge replaces the whole llm_fit key,
        # so sibling jobs' entries (already in llm_fit) survive.
        database.execute(
            "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb "
            "WHERE candidate_id = %s AND snapshot_version = "
            "(SELECT MAX(snapshot_version) FROM candidate_snapshots WHERE candidate_id = %s)",
            [json.dumps({"llm_fit": llm_fit}), candidate_id, candidate_id],
        )
    return fit


def compute_experience_score(cand_profile: dict, job_parsed: dict) -> float:
    """Compute experience score based on candidate years of experience (0-100)."""
    try:
        cand_exp = int(cand_profile.get("years_experience") or 0)
    except:
        cand_exp = 0

    try:
        required = int(job_parsed.get("years_experience_min") or 0)
    except (TypeError, ValueError):
        required = 0

    # When years of experience couldn't be parsed (0), fall back to resume signals.
    # Use word-boundary matching so "international" / "internal" don't match "intern".
    if cand_exp == 0:
        raw_text = (cand_profile.get("raw_text") or "").lower()
        if re.search(r"\b(intern|internship|fresher|entry[- ]level|student|recent graduate)\b", raw_text):
            return 15.0
        return 20.0

    # Score relative to what the job actually requires: meeting/exceeding the
    # minimum scores 100, and candidates below it scale down proportionally.
    if required > 0:
        return round(min(100.0, (cand_exp / required) * 100.0), 1)

    # No minimum specified on the job — fall back to an absolute experience ladder.
    if cand_exp >= 7:
        return 100.0
    elif cand_exp >= 4:
        return 80.0
    elif cand_exp >= 2:
        return 60.0
    elif cand_exp == 1:
        return 40.0
    else:
        return 20.0


def get_cached_explanation(database, job_version_id: str, snapshot_id: str) -> str | None:
    row = database.fetchone(
        """
        SELECT o.explanation_text 
        FROM ranking_run_outputs o
        JOIN ranking_runs r ON o.ranking_run_id = r.id
        WHERE r.job_version_id = %s AND o.candidate_snapshot_id = %s AND o.explanation_text IS NOT NULL AND o.explanation_text != ''
        ORDER BY r.created_at DESC LIMIT 1
        """,
        [job_version_id, snapshot_id]
    )
    return row[0] if row else None


@router.get("", response_model=RankingResponse)
def get_rankings(job_id: str, security: SecurityContext = Depends(get_security_context)) -> RankingResponse:
    import logging
    logger = logging.getLogger(__name__)

    database = get_database(settings.database_dsn)
    
    # 1. Fetch Job Version scoped to org_id
    job_row = database.fetchone(
        "SELECT jv.title, jv.parsed_json, jv.raw_text, jv.id FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.job_id = %s AND j.org_id = %s ORDER BY jv.version DESC LIMIT 1",
        [job_id, security.org_id]
    )
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_title, parsed_json, job_raw_text, job_version_id = job_row
    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except json.JSONDecodeError:
            parsed_json = {}

    # Define list of job skills for category calculations
    must_have = parsed_json.get("must_have_skills") or []
    nice_to_have = parsed_json.get("nice_to_have_skills") or []
    job_skills_list = must_have + nice_to_have

    # 2. Fetch current candidate snapshots for this job
    candidate_rows = database.fetchall(
        """
        SELECT c.id, s.profile_json, s.id
        FROM candidates c
        JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE c.status IN ('extracted', 'interview', 'interviewing', 'selected', 'rejected')
          AND s.profile_json->>'job_id' = %s
          AND c.org_id = %s
        """,
        [job_id, security.org_id]
    )
    current_snapshots = {row[2] for row in candidate_rows}
    
    # 3. Check for the latest completed ranking run for this job version
    latest_run_row = database.fetchone(
        """
        SELECT id FROM ranking_runs 
        WHERE job_version_id = %s AND status = 'completed' AND org_id = %s
        ORDER BY created_at DESC LIMIT 1
        """,
        [job_version_id, security.org_id]
    )
    
    if latest_run_row:
        latest_run_id = latest_run_row[0]
        repo = RankingRepository(database)
        run_outputs = repo.list_outputs(latest_run_id)
        if run_outputs:
            current_snapshots_str = {str(sid) for sid in current_snapshots}
            # Render the latest run intersected with the CURRENT roster: candidates removed
            # since the run are filtered out; candidates added since (not yet scored) simply
            # don't appear until the post-upload incremental run includes them. The ranking is
            # never blanked just because a new candidate was added.
            if current_snapshots_str:
                ranked_candidates = []
                sorted_outputs = sorted(run_outputs, key=lambda x: x.rank)
                for o in sorted_outputs:
                    if str(o.candidate_snapshot_id) not in current_snapshots_str:
                        continue  # candidate no longer exists for this job
                    cand_row = database.fetchone(
                        "SELECT cs.candidate_id, cs.profile_json, c.status "
                        "FROM candidate_snapshots cs JOIN candidates c ON c.id = cs.candidate_id "
                        "WHERE cs.id = %s",
                        [o.candidate_snapshot_id]
                    )
                    cand_id = cand_row[0] if cand_row else ""
                    profile_json = cand_row[1] if cand_row and cand_row[1] else {}
                    cand_status = cand_row[2] if cand_row else None
                    if isinstance(profile_json, str):
                        try:
                            profile_json = json.loads(profile_json)
                        except:
                            profile_json = {}

                    cand_name = profile_json.get("name", "Unknown Candidate")

                    # Category scores from the cached LLM-judged fit (read-only; no LLM call)
                    fit = get_fit(database, None, cand_id, profile_json, parsed_json, job_version_id, force=False)
                    hard_skills_score = fit["hard_skills"]
                    soft_skills_score = fit["soft_skills"]
                    experience_score = compute_experience_score(profile_json, parsed_json)
                    domain_score = fit["domain_knowledge"]

                    ranked_candidates.append(
                        RankingCandidate(
                            candidate_id=str(cand_id),
                            candidate_name=cand_name,
                            score=o.final_score,
                            rank=o.rank,
                            explanation_text=o.explanation_text,
                            category_scores={
                                "hard_skills": hard_skills_score,
                                "soft_skills": soft_skills_score,
                                "experience": experience_score,
                                "domain_knowledge": domain_score
                            },
                            status=cand_status,
                        )
                    )
                if ranked_candidates:
                    logger.info("Returning ranking run %s (%d of %d run outputs still current)", latest_run_id, len(ranked_candidates), len(run_outputs))
                    return RankingResponse(run_id=str(latest_run_id), candidates=ranked_candidates)

    # If no cached run exists or it doesn't match the current candidate set, return empty list
    logger.info("No matching cached ranking run found for job version %s", job_version_id)
    return RankingResponse(run_id="", candidates=[])


@router.post("", response_model=RankingResponse)
def generate_rankings(job_id: str, security: SecurityContext = Depends(get_security_context)) -> RankingResponse:
    """Explicit (re)ranking via the Recalculate button — re-judges every candidate (force=True)."""
    return run_ranking(job_id, security, force=True)


def run_ranking(job_id: str, security: SecurityContext, force: bool = True) -> RankingResponse:
    """Score the current roster for a job and persist a ranking run.

    force=True re-judges every candidate (explicit Recalculate, e.g. after a job edit or a
    model change). force=False reuses cached per-candidate fits and only judges candidates
    not yet scored — the cheap incremental run triggered in the background after an upload.
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    database = get_database(settings.database_dsn)
    
    # 1. Fetch Job Version scoped to org_id
    job_row = database.fetchone(
        "SELECT jv.title, jv.parsed_json, jv.raw_text, jv.id FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.job_id = %s AND j.org_id = %s ORDER BY jv.version DESC LIMIT 1",
        [job_id, security.org_id]
    )
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_title, parsed_json, job_raw_text, job_version_id = job_row
    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except json.JSONDecodeError:
            parsed_json = {}

    # Define list of job skills for category calculations
    must_have = parsed_json.get("must_have_skills") or []
    nice_to_have = parsed_json.get("nice_to_have_skills") or []
    job_skills = [s.lower() for s in (must_have + nice_to_have)]
    job_exp = parsed_json.get("years_experience_min", 0) or 0
    must_have_skills = [s.lower() for s in must_have]
    job_skills_list = must_have + nice_to_have

    # 2. Fetch extracted candidates linked to this job (scoped to org_id)
    candidate_rows = database.fetchall(
        """
        SELECT c.id, s.profile_json, s.id, c.status
        FROM candidates c
        JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE c.status IN ('extracted', 'interview', 'interviewing', 'selected', 'rejected')
          AND s.profile_json->>'job_id' = %s
          AND c.org_id = %s
        """,
        [job_id, security.org_id]
    )
    cand_status_map = {str(row[0]): row[3] for row in candidate_rows}
    ranking_cfg = load_ranking_config(database)

    matcher = MatchingEngine()
    scorer = ScoringEngine()
    decider = DecisionEngine()
    
    gemini_key = os.getenv("GEMINI_API_KEY", settings.gemini_api_key)
    llm = LLMClient(LLMConfig(
        api_key=settings.openai_api_key,
        gemini_api_key=gemini_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
    ))
    explainer = RankingExplanationService(llm)
    # Dedicated temperature-0 client for the fit judge (stable, deterministic scores)
    judge_llm = LLMClient(LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=0.0,
    ))

    # Generate job embedding dynamically
    job_embedding_vector = [0.0] * 768
    try:
        if job_raw_text:
            skills_text = ", ".join(must_have + nice_to_have)
            job_text_input = f"Job Title: {job_title}\nSkills required: {skills_text}\nDescription: {job_raw_text}".strip()
            vectors = llm.embed([job_text_input])
            if vectors:
                job_embedding_vector = vectors[0]
                logger.info("Generated dynamic embedding for job %s", job_id)
    except Exception as e:
        logger.warning("Job embedding generation failed: %s", e)

    # Initialize Ranking Repository and create run
    repo = RankingRepository(database)
    run = repo.create_run(
        org_id=security.org_id,
        job_version_id=job_version_id,
        scoring_version="v0",
        created_by=security.user_id
    )
    run_id = run.run_id
            
    decision_inputs = []
    scored_candidates = {}
    candidate_snapshots = {}
    
    for row in candidate_rows:
        cand_id = row[0]
        profile = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
        snap_id = row[2]
        candidate_snapshots[cand_id] = snap_id
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
        
        job_score_features = {
            "skills": 1.0,
            "experience": 1.0,
            "education": 1.0
        }
        
        # LLM-judged fit (fresh per run, cached per job_version_id)
        fit = get_fit(database, judge_llm, cand_id, profile, parsed_json, job_version_id, force=force)
        cand_skills_list = profile.get("skills", [])
        cand_domains_list = profile.get("domains", [])

        # Include individual must-haves in features (3-way reconciliation, robust to drift/omission)
        for mh in must_have_skills:
            cand_score_features[mh] = 1.0 if _requirement_satisfied(mh, fit["matched_skills"], fit["missing_skills"], cand_skills_list, cand_domains_list) else 0.0
            job_score_features[mh] = 1.0
        
        # Fetch candidate embedding from DB
        cand_embedding_vector = [0.0] * 768
        emb_row = database.fetchone(
            "SELECT embedding FROM candidate_embeddings WHERE candidate_snapshot_id = %s",
            [snap_id]
        )
        if emb_row and emb_row[0]:
            val = emb_row[0]
            if isinstance(val, str):
                val = [float(x) for x in val.strip("[]").split(",") if x.strip()]
            cand_embedding_vector = val
            logger.info("Loaded real embedding for candidate snapshot %s", snap_id)

        # Category scores: skills/soft/domain from the LLM judge, experience deterministic
        hard_skills_score = fit["hard_skills"]
        soft_skills_score = fit["soft_skills"]
        experience_score = compute_experience_score(profile, parsed_json)
        domain_score = fit["domain_knowledge"]

        name_lower = cand_name.lower()

        # Run Matching
        match_result = matcher.match(
            MatchInput(
                candidate_features=cand_score_features,
                job_features=job_score_features,
                taxonomy_links=[],
                candidate_embedding=cand_embedding_vector,
                job_embedding=job_embedding_vector
            )
        )
        
        # Overwrite scores to use the correct category values for final scoring
        semantic_sim = match_result.scores.get("semantic_similarity", 0.0)
        match_result.scores["skills"] = hard_skills_score / 100.0
        
        # Apply Gating logic
        if match_result.scores["skills"] < ranking_cfg["skills_gate"]:
            match_result.scores["experience"] = 0.0
            match_result.scores["education"] = 0.0
        else:
            match_result.scores["experience"] = experience_score / 100.0
            match_result.scores["education"] = domain_score / 100.0

        match_result.scores["semantic_similarity"] = 0.7 * (soft_skills_score / 100.0) + 0.3 * semantic_sim

        score_result = scorer.score(
            ScoreInput(
                match_scores=match_result.scores,
                weights=ranking_cfg["weights"],
                must_have=must_have_skills,
                evidence={key: [ScoreEvidence(source="match", text="")] for key in match_result.scores}
            )
        )
        
        cand_category_scores = {
            "hard_skills": hard_skills_score,
            "soft_skills": soft_skills_score,
            "experience": experience_score,
            "domain_knowledge": domain_score
        }

        # Persist feature contributions
        repo.write_feature_contributions(
            run_id=run_id,
            candidate_id=snap_id,
            contributions=score_result.feature_contributions,
        )
        
        scored_candidates[cand_id] = {
            "score": score_result.final_score,
            "name": cand_name,
            "cand_features": cand_score_features,
            "job_features": job_score_features,
            "category_scores": cand_category_scores
        }
        decision_inputs.append(
            DecisionInput(
                candidate_id=cand_id,
                final_score=score_result.final_score,
                passed_must_have=score_result.passed_must_have,
                category_scores=cand_category_scores
            )
        )
        
    # Rank
    decisions = decider.rank(decision_inputs, threshold=ranking_cfg["shortlist_threshold"])
    
    ranked = []
    output_records = []
    for d in decisions:
        cand_info = scored_candidates[d.candidate_id]
        snap_id = candidate_snapshots[d.candidate_id]
        
        # Cache Lookup: Check for previously generated explanation
        explanation = get_cached_explanation(database, job_version_id, snap_id)
        if explanation:
            logger.info("Reusing cached explanation for snapshot %s", snap_id)
        else:
            # Generate explanation via LLM ONLY if rank is <= 5, otherwise use fast fallback
            if d.rank <= 5:
                explanation = explainer.generate(
                    candidate_id=d.candidate_id,
                    job_features=cand_info["job_features"],
                    candidate_features=cand_info["cand_features"],
                    score=cand_info["score"],
                    decision=d.decision,
                    triggers=d.triggers,
                    rank=d.rank,
                    candidate_name=cand_info["name"],
                )
            else:
                explanation = explainer._generate_fallback(
                    score=cand_info["score"],
                    decision=d.decision,
                    triggers=d.triggers,
                    candidate_features=cand_info["cand_features"],
                    job_features=cand_info["job_features"],
                    rank=d.rank,
                    candidate_name=cand_info["name"],
                )
        
        ranked.append(
            RankingCandidate(
                candidate_id=str(d.candidate_id),
                candidate_name=cand_info["name"],
                score=cand_info["score"],
                rank=d.rank,
                explanation_text=explanation,
                category_scores=cand_info.get("category_scores", {}),
                status=cand_status_map.get(str(d.candidate_id)),
            )
        )

        output_records.append(
            RankingOutputRecord(
                run_id=run_id,
                candidate_snapshot_id=snap_id,
                final_score=cand_info["score"],
                rank=d.rank,
                decision=d.decision,
                explanation_text=explanation,
            )
        )
        
    repo.write_outputs(output_records)
    
    return RankingResponse(run_id=str(run_id), candidates=ranked)


@router.post("/simulate", response_model=RankingResponse)
def simulate_ranking(
    job_id: str,
    payload: SimulateRankingRequest,
    security: SecurityContext = Depends(get_security_context)
) -> RankingResponse:
    import logging
    logger = logging.getLogger(__name__)
    matcher = MatchingEngine()
    scorer = ScoringEngine()
    decider = DecisionEngine()
    database = get_database(settings.database_dsn)
    repo = RankingRepository(database)
    ranking_cfg = load_ranking_config(database)
    gemini_key = os.getenv("GEMINI_API_KEY", settings.gemini_api_key)
    llm = LLMClient(LLMConfig(
        api_key=settings.openai_api_key,
        gemini_api_key=gemini_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
    ))
    explainer = RankingExplanationService(llm)

    # Fetch the latest job version id for this job_id (scoped to org_id)
    job_version_row = database.fetchone(
        """
        SELECT jv.id, jv.title, jv.parsed_json, jv.raw_text
        FROM job_versions jv 
        JOIN jobs j ON jv.job_id = j.id 
        WHERE jv.job_id = %s AND j.org_id = %s 
        ORDER BY jv.version DESC LIMIT 1
        """,
        [job_id, security.org_id]
    )
    if not job_version_row:
        fallback_row = database.fetchone(
            "SELECT jv.id, jv.title, jv.parsed_json, jv.raw_text FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.id = %s AND j.org_id = %s",
            [job_id, security.org_id]
        )
        if not fallback_row:
            raise HTTPException(status_code=404, detail=f"No job version found for job ID {job_id}")
        job_version_id = job_id
        job_title = fallback_row[1] or "Unknown Job"
        parsed_json = fallback_row[2] or {}
        job_raw_text = fallback_row[3] or ""
    else:
        job_version_id = job_version_row[0]
        job_title = job_version_row[1] or "Unknown Job"
        parsed_json = job_version_row[2] or {}
        job_raw_text = job_version_row[3] or ""

    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except json.JSONDecodeError:
            parsed_json = {}

    run = repo.create_run(
        org_id=security.org_id,
        job_version_id=job_version_id,
        scoring_version="v0",
        created_by=security.user_id
    )
    run_id = run.run_id

    # Standardize weights keys
    weights = dict(payload.weights)
    if "semantic" in weights and "semantic_similarity" not in weights:
        weights["semantic_similarity"] = weights.pop("semantic")

    ranked = []
    output_records = []

    # Case 1: Candidates are provided in the payload (original simulation logic)
    if payload.candidates:
        decision_inputs = []
        scored = {}
        scored_category = {}
        candidate_lookup = {c.candidate_id: c for c in payload.candidates}

        for candidate in payload.candidates:
            snap_row = database.fetchone(
                "SELECT s.id, s.profile_json FROM candidate_snapshots s JOIN candidates c ON s.candidate_id = c.id WHERE s.candidate_id = %s AND c.org_id = %s ORDER BY s.snapshot_version DESC LIMIT 1",
                [candidate.candidate_id, security.org_id]
            )
            snap_id = snap_row[0] if snap_row else candidate.candidate_id
            profile_json = snap_row[1] if snap_row and snap_row[1] else {}
            if isinstance(profile_json, str):
                try:
                    profile_json = json.loads(profile_json)
                except Exception:
                    profile_json = {}

            fit = get_fit(database, llm, candidate.candidate_id, profile_json, parsed_json, job_version_id, force=False)
            hard_skills_score = fit["hard_skills"]
            soft_skills_score = fit["soft_skills"]
            experience_score = compute_experience_score(profile_json, parsed_json)
            domain_score = fit["domain_knowledge"]

            match_result = matcher.match(
                MatchInput(
                    candidate_features=candidate.candidate_features,
                    job_features=candidate.job_features,
                    taxonomy_links=candidate.taxonomy_links,
                    candidate_embedding=candidate.candidate_embedding,
                    job_embedding=candidate.job_embedding,
                )
            )

            # Overwrite scores to use the correct category values for final scoring
            semantic_sim = match_result.scores.get("semantic_similarity", 0.0)
            match_result.scores["skills"] = hard_skills_score / 100.0
            
            # Apply Gating logic
            if match_result.scores["skills"] < ranking_cfg["skills_gate"]:
                match_result.scores["experience"] = 0.0
                match_result.scores["education"] = 0.0
            else:
                match_result.scores["experience"] = experience_score / 100.0
                match_result.scores["education"] = domain_score / 100.0

            match_result.scores["semantic_similarity"] = 0.7 * (soft_skills_score / 100.0) + 0.3 * semantic_sim

            score_result = scorer.score(
                ScoreInput(
                    match_scores=match_result.scores,
                    weights=weights,
                    must_have=payload.must_have or [],
                    evidence={key: [ScoreEvidence(source="match", text="")] for key in match_result.scores},
                )
            )
            scored[candidate.candidate_id] = score_result.final_score
            
            repo.write_feature_contributions(
                run_id=run_id,
                candidate_id=snap_id,
                contributions=score_result.feature_contributions,
            )

            cand_category_scores = {
                "hard_skills": hard_skills_score,
                "soft_skills": soft_skills_score,
                "experience": experience_score,
                "domain_knowledge": domain_score
            }
            scored_category[candidate.candidate_id] = cand_category_scores

            decision_inputs.append(
                DecisionInput(
                    candidate_id=candidate.candidate_id,
                    final_score=score_result.final_score,
                    passed_must_have=score_result.passed_must_have,
                    category_scores=cand_category_scores,
                )
            )

        decisions = decider.rank(decision_inputs, threshold=payload.threshold or ranking_cfg["shortlist_threshold"])
        
        for item in decisions:
            cand_input = candidate_lookup[item.candidate_id]
            snap_row = database.fetchone(
                "SELECT s.id, s.profile_json, c.status FROM candidate_snapshots s JOIN candidates c ON s.candidate_id = c.id WHERE s.candidate_id = %s AND c.org_id = %s ORDER BY s.snapshot_version DESC LIMIT 1",
                [item.candidate_id, security.org_id]
            )
            snap_id = snap_row[0] if snap_row else item.candidate_id
            profile_json = snap_row[1] if snap_row and snap_row[1] else {}
            cand_status = snap_row[2] if snap_row else None
            if isinstance(profile_json, str):
                try:
                    profile_json = json.loads(profile_json)
                except Exception:
                    profile_json = {}
            
            candidate_name = profile_json.get("name") or "Unknown Candidate"
            cand_category_scores = scored_category.get(item.candidate_id, {})

            # Cache Lookup: Check for previously generated explanation
            explanation = get_cached_explanation(database, job_version_id, snap_id)
            if explanation:
                logger.info("Reusing cached explanation for snapshot %s in simulation", snap_id)
            else:
                # Generate explanation via LLM ONLY if rank is <= 5, otherwise use fast fallback
                if item.rank <= 5:
                    explanation = explainer.generate(
                        candidate_id=item.candidate_id,
                        job_features=cand_input.job_features,
                        candidate_features=cand_input.candidate_features,
                        score=scored.get(item.candidate_id, 0.0),
                        decision=item.decision,
                        triggers=item.triggers,
                        rank=item.rank,
                        candidate_name=candidate_name,
                    )
                else:
                    explanation = explainer._generate_fallback(
                        score=scored.get(item.candidate_id, 0.0),
                        decision=item.decision,
                        triggers=item.triggers,
                        candidate_features=cand_input.candidate_features,
                        job_features=cand_input.job_features,
                        rank=item.rank,
                        candidate_name=candidate_name,
                    )
            
            ranked.append(
                RankingCandidate(
                    candidate_id=item.candidate_id,
                    candidate_name=candidate_name,
                    score=scored.get(item.candidate_id, 0.0),
                    rank=item.rank,
                    explanation_text=explanation,
                    category_scores=cand_category_scores,
                    status=cand_status,
                )
            )
            output_records.append(
                RankingOutputRecord(
                    run_id=run_id,
                    candidate_snapshot_id=snap_id,
                    final_score=scored.get(item.candidate_id, 0.0),
                    rank=item.rank,
                    decision=item.decision,
                    explanation_text=explanation,
                )
            )

    # Case 2: Candidates are not provided (UI simulation, load from DB)
    else:
        must_have = parsed_json.get("must_have_skills") or []
        nice_to_have = parsed_json.get("nice_to_have_skills") or []
        job_skills = [s.lower() for s in (must_have + nice_to_have)]
        job_exp = parsed_json.get("years_experience_min", 0) or 0
        must_have_skills = [s.lower() for s in must_have]

        candidate_rows = database.fetchall(
            """
            SELECT c.id, s.profile_json, s.id, c.status
            FROM candidates c
            JOIN candidate_snapshots s ON c.id = s.candidate_id
            WHERE c.status IN ('extracted', 'interview', 'interviewing', 'selected', 'rejected')
              AND s.profile_json->>'job_id' = %s
              AND c.org_id = %s
            """,
            [job_id, security.org_id]
        )
        cand_status_map = {str(row[0]): row[3] for row in candidate_rows}

        job_embedding_vector = [0.0] * 768
        try:
            if job_raw_text:
                skills_text = ", ".join(must_have + nice_to_have)
                job_text_input = f"Job Title: {job_title}\nSkills required: {skills_text}\nDescription: {job_raw_text}".strip()
                vectors = llm.embed([job_text_input])
                if vectors:
                    job_embedding_vector = vectors[0]
        except Exception as e:
            logger.warning("Job embedding generation failed: %s", e)

        scored_candidates = {}
        candidate_snapshots = {}
        decision_inputs = []

        for row in candidate_rows:
            cand_id = row[0]
            profile_json = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
            snap_id = row[2]
            candidate_snapshots[cand_id] = snap_id
            cand_name = profile_json.get("name", "Unknown Candidate")
            
            cand_skills = [s.lower() for s in profile_json.get("skills", [])]
            cand_exp = profile_json.get("years_experience", 0)
            
            skill_match = len(set(cand_skills).intersection(set(job_skills))) / len(job_skills) if job_skills else 1.0
            exp_match = min(1.0, cand_exp / job_exp) if job_exp else 1.0
            
            cand_score_features = {
                "skills": skill_match,
                "experience": exp_match,
                "education": 1.0
            }
            
            job_score_features = {
                "skills": 1.0,
                "experience": 1.0,
                "education": 1.0
            }
            
            fit = get_fit(database, llm, cand_id, profile_json, parsed_json, job_version_id, force=False)
            for mh in must_have_skills:
                cand_score_features[mh] = 1.0 if _requirement_satisfied(mh, fit["matched_skills"], fit["missing_skills"], profile_json.get("skills", []), profile_json.get("domains", [])) else 0.0
                job_score_features[mh] = 1.0

            cand_embedding_vector = [0.0] * 768
            emb_row = database.fetchone(
                "SELECT embedding FROM candidate_embeddings WHERE candidate_snapshot_id = %s",
                [snap_id]
            )
            if emb_row and emb_row[0]:
                val = emb_row[0]
                if isinstance(val, str):
                    val = [float(x) for x in val.strip("[]").split(",") if x.strip()]
                cand_embedding_vector = val

            job_skills_list = (parsed_json.get("must_have_skills") or []) + (parsed_json.get("nice_to_have_skills") or [])
            hard_skills_score = fit["hard_skills"]
            soft_skills_score = fit["soft_skills"]
            experience_score = compute_experience_score(profile_json, parsed_json)
            domain_score = fit["domain_knowledge"]

            match_result = matcher.match(
                MatchInput(
                    candidate_features=cand_score_features,
                    job_features=job_score_features,
                    taxonomy_links=[],
                    candidate_embedding=cand_embedding_vector,
                    job_embedding=job_embedding_vector
                )
            )
            
            # Overwrite scores to use the correct category values for final scoring
            semantic_sim = match_result.scores.get("semantic_similarity", 0.0)
            match_result.scores["skills"] = hard_skills_score / 100.0
            
            # Apply Gating logic
            if match_result.scores["skills"] < ranking_cfg["skills_gate"]:
                match_result.scores["experience"] = 0.0
                match_result.scores["education"] = 0.0
            else:
                match_result.scores["experience"] = experience_score / 100.0
                match_result.scores["education"] = domain_score / 100.0

            match_result.scores["semantic_similarity"] = 0.7 * (soft_skills_score / 100.0) + 0.3 * semantic_sim

            score_result = scorer.score(
                ScoreInput(
                    match_scores=match_result.scores,
                    weights=weights,
                    must_have=must_have_skills,
                    evidence={key: [ScoreEvidence(source="match", text="")] for key in match_result.scores}
                )
            )

            cand_category_scores = {
                "hard_skills": hard_skills_score,
                "soft_skills": soft_skills_score,
                "experience": experience_score,
                "domain_knowledge": domain_score
            }

            repo.write_feature_contributions(
                run_id=run_id,
                candidate_id=snap_id,
                contributions=score_result.feature_contributions,
            )
            
            scored_candidates[cand_id] = {
                "score": score_result.final_score,
                "name": cand_name,
                "cand_features": cand_score_features,
                "job_features": job_score_features,
                "category_scores": cand_category_scores
            }
            decision_inputs.append(
                DecisionInput(
                    candidate_id=cand_id,
                    final_score=score_result.final_score,
                    passed_must_have=score_result.passed_must_have,
                    category_scores=cand_category_scores
                )
            )

        decisions = decider.rank(decision_inputs, threshold=payload.threshold or ranking_cfg["shortlist_threshold"])
        
        for d in decisions:
            cand_info = scored_candidates[d.candidate_id]
            snap_id = candidate_snapshots[d.candidate_id]
            
            # Cache Lookup: Check for previously generated explanation
            explanation = get_cached_explanation(database, job_version_id, snap_id)
            if explanation:
                logger.info("Reusing cached explanation for snapshot %s in simulation (no candidates payload)", snap_id)
            else:
                # Generate explanation via LLM ONLY if rank is <= 5, otherwise use fast fallback
                if d.rank <= 5:
                    explanation = explainer.generate(
                        candidate_id=d.candidate_id,
                        job_features=cand_info["job_features"],
                        candidate_features=cand_info["cand_features"],
                        score=cand_info["score"],
                        decision=d.decision,
                        triggers=d.triggers,
                        rank=d.rank,
                        candidate_name=cand_info["name"],
                    )
                else:
                    explanation = explainer._generate_fallback(
                        score=cand_info["score"],
                        decision=d.decision,
                        triggers=d.triggers,
                        candidate_features=cand_info["cand_features"],
                        job_features=cand_info["job_features"],
                        rank=d.rank,
                        candidate_name=cand_info["name"],
                    )
            
            ranked.append(
                RankingCandidate(
                    candidate_id=str(d.candidate_id),
                    candidate_name=cand_info["name"],
                    score=cand_info["score"],
                    rank=d.rank,
                    explanation_text=explanation,
                    category_scores=cand_info.get("category_scores", {}),
                    status=cand_status_map.get(str(d.candidate_id)),
                )
            )

            output_records.append(
                RankingOutputRecord(
                    run_id=run_id,
                    candidate_snapshot_id=snap_id,
                    final_score=cand_info["score"],
                    rank=d.rank,
                    decision=d.decision,
                    explanation_text=explanation,
                )
            )

    repo.write_outputs(output_records)
    return RankingResponse(run_id=str(run_id), candidates=ranked)


@router.post("/{run_id}/overrides", status_code=201)
def create_override(
    job_id: str,
    run_id: str,
    payload: OverrideRequest,
    security: SecurityContext = Depends(get_security_context)
) -> dict:
    database = get_database(settings.database_dsn)
    repo = RankingRepository(database)
    
    # Verify run_id belongs to org_id
    run_row = database.fetchone("SELECT id FROM ranking_runs WHERE id = %s AND org_id = %s", [run_id, security.org_id])
    if not run_row:
        raise HTTPException(status_code=404, detail="Ranking run not found")

    repo.write_override(
        run_id=run_id,
        candidate_id=payload.candidate_id,
        old_rank=payload.old_rank,
        new_rank=payload.new_rank,
        reason=payload.reason,
        user_id=security.user_id
    )
    return {"status": "success"}


@router.get("/{run_id}/bias")
def get_bias_analysis(
    job_id: str,
    run_id: str,
    security: SecurityContext = Depends(get_security_context)
) -> dict:
    database = get_database(settings.database_dsn)
    
    # 1. Verify run_id belongs to org_id
    run_row = database.fetchone("SELECT id FROM ranking_runs WHERE id = %s AND org_id = %s", [run_id, security.org_id])
    if not run_row:
        raise HTTPException(status_code=404, detail="Ranking run not found")

    # 2. Fetch candidate scores and profiles for this run
    rows = database.fetchall(
        """
        SELECT o.candidate_snapshot_id, o.final_score, s.profile_json
        FROM ranking_run_outputs o
        JOIN candidate_snapshots s ON o.candidate_snapshot_id = s.id
        WHERE o.ranking_run_id = %s
        """,
        [run_id]
    )

    from services.bias.analyzer import BiasAnalyzer, CandidateProfile
    
    profiles = []
    scores = []
    for row in rows:
        snap_id = str(row[0])
        final_score = float(row[1])
        profile_json = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
        
        profiles.append(CandidateProfile(
            candidate_snapshot_id=snap_id,
            final_score=final_score,
            education_level=profile_json.get("education_level", "unknown"),
            years_experience=profile_json.get("years_experience", 0),
            career_trajectory=profile_json.get("career_trajectory", "unknown"),
            domains=profile_json.get("domains", [])
        ))
        scores.append(final_score)

    # 3. Analyze using BiasAnalyzer
    analyzer = BiasAnalyzer()
    bias_result = analyzer.analyze(scores, profiles)

    # 4. Persist metrics to database
    existing = database.fetchone("SELECT id FROM bias_analysis_results WHERE ranking_run_id = %s", [run_id])
    if existing:
        database.execute(
            "UPDATE bias_analysis_results SET metrics_json = %s WHERE ranking_run_id = %s",
            [json.dumps(bias_result.metrics), run_id]
        )
    else:
        database.execute(
            "INSERT INTO bias_analysis_results (ranking_run_id, metrics_json) VALUES (%s, %s)",
            [run_id, json.dumps(bias_result.metrics)]
        )

    # 5. Resolve candidate names for hidden gems
    hidden_gems_info = []
    for snap_id in bias_result.hidden_gems:
        cand_row = database.fetchone("SELECT profile_json->>'name' FROM candidate_snapshots WHERE id = %s", [snap_id])
        name = cand_row[0] if cand_row else "Unknown Candidate"
        hidden_gems_info.append({"snapshot_id": snap_id, "name": name})

    return {
        "metrics": bias_result.metrics,
        "flags": [
            {
                "flag_type": f.flag_type,
                "severity": f.severity,
                "message": f.message
            } for f in bias_result.flags
        ],
        "hidden_gems": hidden_gems_info
    }

