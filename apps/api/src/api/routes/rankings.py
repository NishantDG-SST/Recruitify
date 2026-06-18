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


# ---------------------------------------------------------------------------
# Semantic skill matching helpers
# ---------------------------------------------------------------------------

_SKILL_SYNONYMS: dict[str, set[str]] = {
    "python": {"python3", "python2", "cpython", "python programming"},
    "javascript": {"js", "ecmascript", "es6", "es2015", "vanilla js"},
    "typescript": {"ts"},
    "react": {"reactjs", "react.js", "react js"},
    "angular": {"angularjs", "angular.js"},
    "vue": {"vuejs", "vue.js"},
    "node": {"nodejs", "node.js", "node js"},
    "express": {"expressjs", "express.js"},
    "nextjs": {"next.js", "next js", "next"},
    "aws": {"amazon web services", "amazon aws", "cloud computing"},
    "gcp": {"google cloud", "google cloud platform", "vertex ai", "bigquery", "gke"},
    "azure": {"microsoft azure", "azure cloud"},
    "docker": {"containerization", "containers"},
    "kubernetes": {"k8s", "container orchestration"},
    "terraform": {"infrastructure as code", "iac"},
    "postgres": {"postgresql", "pg"},
    "mysql": {"mariadb"},
    "mongodb": {"mongo"},
    "redis": {"caching"},
    "kafka": {"apache kafka", "event streaming"},
    "ci/cd": {"continuous integration", "continuous deployment", "cicd", "ci cd", "devops"},
    "git": {"github", "gitlab", "version control", "source control"},
    "machine learning": {"ml", "deep learning", "ai", "artificial intelligence"},
    "rest": {"restful", "rest api", "restful api"},
    "graphql": {"graph ql"},
    "microservices": {"micro services", "microservice architecture"},
    "agile": {"scrum", "kanban"},
    "pandas": {"data analysis"},
    "spark": {"apache spark", "pyspark"},
    "java": {"jvm", "j2ee"},
    "spring": {"spring boot", "spring framework", "springboot"},
    "c++": {"cpp", "c plus plus"},
    "c#": {"csharp", "c sharp", ".net", "dotnet"},
    "ruby": {"ruby on rails", "rails", "ror"},
    "go": {"golang"},
    "rust": {"rustlang"},
}

# Build reverse lookup
_SKILL_CANON: dict[str, str] = {}
for _canon, _syns in _SKILL_SYNONYMS.items():
    _SKILL_CANON[_canon] = _canon
    for _s in _syns:
        _SKILL_CANON[_s] = _canon


def _canonicalize(skill: str) -> str:
    s = skill.lower().strip()
    return _SKILL_CANON.get(s, s)


def _tokens(text: str) -> set[str]:
    """Split a skill/phrase into whole-word tokens (keeps + and # for c++/c#)."""
    return {t for t in re.split(r"[^a-z0-9+#]+", text.lower()) if t}


def check_candidate_has_requirement(req: str, cand_skills: list[str], cand_domains: list[str], cand_raw_text: str = "") -> bool:
    req_clean = req.lower().strip()

    cand_skills_clean = [s.lower().strip() for s in cand_skills]
    cand_skills_canon = {_canonicalize(s) for s in cand_skills_clean}
    req_canon = _canonicalize(req_clean)

    if req_canon in cand_skills_canon or req_clean in cand_skills_clean:
        return True

    # Token-based phrase containment: a requirement matches a skill only when one
    # is a whole-word subset of the other (e.g. "java" ⊆ "core java", "spring" ⊆
    # "spring boot"). This avoids substring false positives like "c" matching
    # "microservices" or "java" matching "javascript".
    req_tokens = _tokens(req_clean)
    req_canon_tokens = _tokens(req_canon)
    for cs in cand_skills_clean:
        cs_tokens = _tokens(cs)
        if req_tokens and (req_tokens <= cs_tokens or cs_tokens <= req_tokens):
            return True
        cs_canon_tokens = _tokens(_canonicalize(cs))
        if req_canon_tokens and (req_canon_tokens <= cs_canon_tokens or cs_canon_tokens <= req_canon_tokens):
            return True

    cand_domains_clean = [d.lower().strip() for d in cand_domains]
    domain_synonyms = {
        "life sciences": {"life sciences", "life science", "biology", "biotech", "biotechnology", "pharmaceuticals", "pharma"},
        "pharmaceutical industries": {"pharmaceuticals", "pharmaceutical", "pharma", "pharmaceutical industry", "pharmaceutical industries", "drug development", "life sciences"},
        "pharmaceuticals": {"pharmaceuticals", "pharmaceutical", "pharma", "pharmaceutical industry", "pharmaceutical industries", "drug development", "life sciences"},
        "contract research organization (cro)": {"contract research organization", "cro", "clinical trials", "clinical trial", "clinical research"},
        "cro": {"contract research organization", "cro", "clinical trials", "clinical trial", "clinical research"},
    }
    
    syns = domain_synonyms.get(req_clean, {req_clean})
    for d in cand_domains_clean:
        if d in syns:
            return True
        for syn in syns:
            if syn in d or d in syn:
                return True
                
    for d in cand_domains_clean:
        if req_clean in d or d in req_clean:
            return True

    if cand_raw_text:
        raw_lower = cand_raw_text.lower()
        # Word-boundary match so "java" does not match "javascript" in resume text.
        for term in {req_clean, *syns}:
            if re.search(r"(?<![a-z0-9+#])" + re.escape(term) + r"(?![a-z0-9+#])", raw_lower):
                return True

    return False


def semantic_skill_match_score(cand_skills: list[str], job_skills: list[str], cand_domains: list[str] = None) -> float:
    """Compute semantic skill match percentage (0-100).
    
    Uses synonym mapping + substring matching as fallback + checks domains.
    """
    if not job_skills:
        return 100.0
    
    cand_domains = cand_domains or []
    matched = 0
    
    for js in job_skills:
        if check_candidate_has_requirement(js, cand_skills, cand_domains):
            matched += 1
            
    return (matched / len(job_skills)) * 100.0


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


def compute_domain_score(cand_profile: dict, job_parsed: dict) -> float:
    """Compute domain knowledge score (0-100).
    
    Uses domain overlap + keyword relevance from resume raw text.
    """
    raw_text = (cand_profile.get("raw_text") or "").lower()
    cand_roles = [r.lower().strip() for r in (cand_profile.get("roles") or [])]
        
    job_domains = [d.lower().strip() for d in (job_parsed.get("domains") or [])]
    if not job_domains:
        # Fallback to software engineering domains if empty
        job_domains = ["software engineering", "systems architecture", "backend engineering", "fullstack development"]
    
    domain_keywords: dict[str, list[str]] = {
        "fintech": ["fintech", "financial", "banking", "payments", "trading", "finance", "investment"],
        "healthcare": ["healthcare", "medical", "health", "clinical", "hospital", "patient", "life sciences", "pharmaceuticals", "pharma", "cro", "clinical trial"],
        "medical services": ["medical services", "medical", "healthcare", "clinical", "hospital", "patient", "life sciences", "pharmaceuticals", "pharma", "cro", "clinical trial"],
        "hospital": ["hospital", "medical", "healthcare", "clinical", "patient"],
        "e-commerce": ["ecommerce", "e-commerce", "retail", "marketplace", "shopping", "commerce"],
        "saas": ["saas", "software as a service", "platform", "b2b", "subscription"],
        "edtech": ["edtech", "education", "learning", "academic"],
        "cybersecurity": ["security", "cybersecurity", "infosec", "vulnerability"],
        "logistics": ["logistics", "supply chain", "warehouse", "shipping"],
        "media": ["media", "content", "publishing", "streaming"],
        "gaming": ["gaming", "game", "esports"],
        "banking": ["banking", "bank", "financial services"],
        "insurance": ["insurance", "insurtech"],
        "telecom": ["telecom", "telecommunications"],
        "energy": ["energy", "oil", "renewable"],
        "automotive": ["automotive", "vehicle", "autonomous"],
        "travel": ["travel", "hospitality", "tourism"],
        "platform engineering": ["platform", "infrastructure", "devops", "sre", "reliability"],
        "high scale": ["scale", "high scale", "distributed", "performance", "scalability", "millions"],
        "software engineering": ["software engineer", "developer", "programming", "software development", "computer science", "coding"],
        "systems architecture": ["system architecture", "scalability", "distributed system", "microservices"],
        "backend engineering": ["backend", "api", "database", "sql", "server"],
        "fullstack development": ["fullstack", "frontend", "backend", "web development", "react", "node"],
    }
    
    cand_domains = [d.lower().strip() for d in (cand_profile.get("domains") or [])]
    
    matched = 0
    for jd in job_domains:
        # Direct match
        if jd in cand_domains:
            matched += 1
            continue
        
        # Keyword-based relevance from raw text and roles
        keywords = domain_keywords.get(jd, [jd])
        found = False
        for kw in keywords:
            if kw in raw_text or any(kw in role for role in cand_roles):
                found = True
                break
        if found:
            matched += 1
            
    score = (matched / len(job_domains)) * 100.0
    return score


def compute_soft_skills_score(cand_profile: dict, job_parsed: dict) -> float:
    """Compute soft skills match score (0-100).
    
    Uses direct matching + inference from resume action verbs/phrases.
    """
    raw_text = (cand_profile.get("raw_text") or "").lower()
    cand_soft = {s.lower().strip() for s in (cand_profile.get("soft_skills") or [])}

    leadership_signals =["led team", "managed team", "team lead", "head of", "director of", "vp of", "chief", "founded", "built team", "leadership", "manager", "lead engineer", "management"]
    mentoring_signals = ["mentored", "coached", "trained", "onboarded", "junior developers", "interns", "mentorship", "mentoring"]
    
    has_leadership = any(sig in raw_text for sig in leadership_signals) or "leadership" in cand_soft
    has_mentoring = any(sig in raw_text for sig in mentoring_signals) or "mentoring" in cand_soft
    
    if not (has_leadership or has_mentoring):
        return 0.0
        
    score = 0.0
    if has_leadership:
        score += 50.0
    if has_mentoring:
        score += 50.0
        
    other_soft = cand_soft - {"leadership", "mentoring"}
    if other_soft:
        score = min(100.0, score + len(other_soft) * 5.0)
        
    return score


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
            run_snapshots = {str(o.candidate_snapshot_id) for o in run_outputs}
            current_snapshots_str = {str(sid) for sid in current_snapshots}
            # Reuse the cached run as long as it covers every current candidate.
            # The run may also contain candidates that have since been removed; those
            # are filtered out below. Only NEW candidates (present now but not in the
            # run) make the run stale and require regeneration.
            if current_snapshots_str and current_snapshots_str <= run_snapshots:
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

                    # Compute category scores
                    hard_skills_score = semantic_skill_match_score(profile_json.get("skills", []), job_skills_list, profile_json.get("domains", []))
                    soft_skills_score = compute_soft_skills_score(profile_json, parsed_json)
                    experience_score = compute_experience_score(profile_json, parsed_json)
                    domain_score = compute_domain_score(profile_json, parsed_json)

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
                logger.info("Returning cached ranking run %s from database", latest_run_id)
                return RankingResponse(run_id=str(latest_run_id), candidates=ranked_candidates)

    # If no cached run exists or it doesn't match the current candidate set, return empty list
    logger.info("No matching cached ranking run found for job version %s", job_version_id)
    return RankingResponse(run_id="", candidates=[])


@router.post("", response_model=RankingResponse)
def generate_rankings(job_id: str, security: SecurityContext = Depends(get_security_context)) -> RankingResponse:
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
        
        # Include individual must-haves in features
        for mh in must_have_skills:
            cand_score_features[mh] = 1.0 if check_candidate_has_requirement(mh, profile.get("skills", []), profile.get("domains", []), profile.get("raw_text", "")) else 0.0
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

        # Calculate consistent category scores
        hard_skills_score = semantic_skill_match_score(profile.get("skills", []), job_skills_list, profile.get("domains", []))
        soft_skills_score = compute_soft_skills_score(profile, parsed_json)
        experience_score = compute_experience_score(profile, parsed_json)
        domain_score = compute_domain_score(profile, parsed_json)

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

            job_skills_list = (parsed_json.get("must_have_skills") or []) + (parsed_json.get("nice_to_have_skills") or [])
            hard_skills_score = semantic_skill_match_score(profile_json.get("skills", []), job_skills_list, profile_json.get("domains", []))
            soft_skills_score = compute_soft_skills_score(profile_json, parsed_json)
            experience_score = compute_experience_score(profile_json, parsed_json)
            domain_score = compute_domain_score(profile_json, parsed_json)

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
            
            for mh in must_have_skills:
                cand_score_features[mh] = 1.0 if check_candidate_has_requirement(mh, profile_json.get("skills", []), profile_json.get("domains", []), profile_json.get("raw_text", "")) else 0.0
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
            hard_skills_score = semantic_skill_match_score(profile_json.get("skills", []), job_skills_list, profile_json.get("domains", []))
            soft_skills_score = compute_soft_skills_score(profile_json, parsed_json)
            experience_score = compute_experience_score(profile_json, parsed_json)
            domain_score = compute_domain_score(profile_json, parsed_json)

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

