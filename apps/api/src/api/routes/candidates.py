import uuid
import json
import time
import logging
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, status, Depends, BackgroundTasks
from typing import List, Any
from pydantic import BaseModel

from schemas.candidates import CandidateDetailResponse, CandidateUploadResponse, CandidateJobProfileResponse
from core.config import settings
from core.database import get_database
from core.auth import SecurityContext, get_security_context
from services.candidates.repository import CandidateRepository
from services.documents.parser import DocumentParser
from services.documents.service import DocumentService
from services.documents.storage_local import LocalDocumentStorage, LocalStorageConfig
from services.events.repository import EventRepository
from services.features.extraction import ExtractionService
from services.llm.client import LLMClient, LLMConfig
from services.taxonomy.normalizer import TaxonomyNormalizer
from services.interviews.generator import InterviewGenerator
from api.routes.rankings import (
    semantic_skill_match_score,
    compute_soft_skills_score,
    compute_domain_score,
    compute_experience_score,
    _canonicalize,
    check_candidate_has_requirement,
)

router = APIRouter(prefix="/jobs/{job_id}/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


def process_candidates_batch_background(
    snapshots_data: list[dict],
    settings_db_dsn: str,
    settings_llm_api_key: str,
    settings_llm_base_url: str,
    settings_llm_model: str,
    settings_embedding_model: str,
):
    from core.database import get_database
    from services.llm.client import LLMClient, LLMConfig
    from services.taxonomy.normalizer import TaxonomyNormalizer
    from services.features.extraction import ExtractionService
    from services.models.embedding_repository import EmbeddingRepository, EmbeddingRecord
    import json
    import time

    database = get_database(settings_db_dsn)
    
    llm_config = LLMConfig(
        api_key=settings_llm_api_key,
        base_url=settings_llm_base_url,
        model=settings_llm_model,
    )
    llm = LLMClient(llm_config)
    normalizer = TaxonomyNormalizer()
    extractor = ExtractionService(normalizer=normalizer, llm_client=llm)

    for snapshot in snapshots_data:
        candidate_id = snapshot["candidate_id"]
        snapshot_id = snapshot["snapshot_id"]
        raw_text = snapshot["raw_text"]
        filename = snapshot["filename"]

        try:
            extracted = extractor.extract(raw_text)
            features = {
                "name": extracted.name,
                "current_role": extracted.current_role,
                "skills": extracted.skills,
                "soft_skills": extracted.soft_skills,
                "roles": extracted.roles,
                "domains": extracted.domains,
                "years_experience": extracted.years_experience,
                "education_level": extracted.education_level,
                "certifications": extracted.certifications,
                "career_trajectory": extracted.career_trajectory,
                "extraction_method": extracted.extraction_method,
            }
            # Update snapshot with extracted features
            database.execute(
                "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb WHERE id = %s",
                [json.dumps(features), snapshot_id]
            )
            # Mark candidate as extracted
            database.execute(
                "UPDATE candidates SET status = 'extracted' WHERE id = %s",
                [candidate_id]
            )
            logger.info("Background extracted %s -> %s", filename, extracted.name)
            
            # Generate and write candidate embeddings
            try:
                skills_text = ", ".join(extracted.skills)
                roles_text = ", ".join(extracted.roles)
                embed_input = f"Skills: {skills_text}\nRoles: {roles_text}\n\n{raw_text}".strip()
                if not embed_input:
                    embed_input = "empty resume"
                
                vectors = llm.embed([embed_input])
                if vectors:
                    EmbeddingRepository(database).write(
                        EmbeddingRecord(
                            candidate_snapshot_id=snapshot_id,
                            embedding_model_id=settings_embedding_model,
                            vector=vectors[0]
                        )
                    )
                    logger.info("Generated background embedding for candidate snapshot %s", snapshot_id)
            except Exception as emb_err:
                logger.warning("Embedding generation failed in background for %s: %s", filename, emb_err)

            # Throttle to avoid Groq rate limits
            time.sleep(0.2)
        except Exception as e:
            logger.error("Background extraction failed for %s: %s", filename, e)
            try:
                database.execute(
                    "UPDATE candidates SET status = 'failed' WHERE id = %s",
                    [candidate_id]
                )
            except Exception as db_err:
                logger.error("Failed to mark candidate status as failed for %s: %s", candidate_id, db_err)


@router.post("", response_model=CandidateUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_candidates(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    security: SecurityContext = Depends(get_security_context)
) -> CandidateUploadResponse:
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    event_repo = EventRepository(database)
    batch_id = str(uuid.uuid4())
    parser = DocumentParser()
    storage = LocalDocumentStorage(LocalStorageConfig(root_dir=Path(settings.storage_root)))
    service = DocumentService(storage=storage, parser=parser)

    snapshots_data = []

    for upload in files:
        content = upload.file.read()
        result = service.ingest(content, upload.filename or "resume", upload.content_type or "")

        # 1. Create snapshot with raw text (initial status set to 'processing' in repository)
        snapshot = candidate_repo.create_snapshot(
            org_id=security.org_id,
            profile_json={"raw_text": result.parsed.text, "warnings": result.parsed.warnings, "job_id": job_id},
            resume_document_id=result.stored.document_id,
        )

        # 2. Log event
        event_repo.append(
            org_id=security.org_id,
            event_type="RESUME_UPLOADED",
            aggregate_type="candidate",
            aggregate_id=snapshot.candidate_id,
            payload={
                "candidate_id": snapshot.candidate_id,
                "candidate_snapshot_id": snapshot.candidate_snapshot_id,
                "job_id": job_id,
                "document_id": result.stored.document_id,
                "user_id": security.user_id
            },
        )

        snapshots_data.append({
            "candidate_id": snapshot.candidate_id,
            "snapshot_id": snapshot.candidate_snapshot_id,
            "raw_text": result.parsed.text,
            "filename": upload.filename or "resume"
        })

    # Schedule the processing batch in the background
    background_tasks.add_task(
        process_candidates_batch_background,
        snapshots_data=snapshots_data,
        settings_db_dsn=settings.database_dsn,
        settings_llm_api_key=settings.llm_api_key,
        settings_llm_base_url=settings.llm_base_url,
        settings_llm_model=settings.llm_model,
        settings_embedding_model=settings.embedding_model,
    )

    return CandidateUploadResponse(batch_id=batch_id)


def _build_llm() -> LLMClient:
    return LLMClient(LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    ))


def _update_latest_snapshot(database, candidate_id: str, patch: dict) -> None:
    """Merge `patch` into the latest snapshot's profile_json for a candidate."""
    database.execute(
        "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb "
        "WHERE candidate_id = %s AND snapshot_version = "
        "(SELECT MAX(snapshot_version) FROM candidate_snapshots WHERE candidate_id = %s)",
        [json.dumps(patch), candidate_id, candidate_id],
    )


def ensure_cv_summary(database, candidate_id: str, profile: dict) -> str:
    """Return the candidate's CV summary, generating and caching it on first use."""
    summary = profile.get("cv_summary") or ""
    if summary:
        return summary
    from services.summaries.generator import SummaryService
    summary, used_llm = SummaryService(_build_llm()).summarize_cv(profile)
    profile["cv_summary"] = summary
    # Only persist real LLM output; fallbacks are shown but not cached so they self-heal.
    if used_llm:
        _update_latest_snapshot(database, candidate_id, {"cv_summary": summary})
    return summary


@router.get("/details/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate_detail(
    job_id: str,
    candidate_id: str,
    security: SecurityContext = Depends(get_security_context)
) -> CandidateDetailResponse:
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    data = candidate_repo.get_candidate(candidate_id, org_id=security.org_id)

    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Candidate not found")

    profile = data.get("profile", {})
    target_job_id = job_id
    try:
        uuid.UUID(target_job_id)
    except (ValueError, TypeError):
        # job_id might be "all" or invalid. Try extracting from profile.
        profile_job_id = profile.get("job_id") or profile.get("job_guid")
        if profile_job_id:
            try:
                uuid.UUID(profile_job_id)
                target_job_id = profile_job_id
            except (ValueError, TypeError):
                target_job_id = None
        else:
            target_job_id = None

    job_requirements = {}
    if target_job_id:
        job_row = database.fetchone(
            "SELECT parsed_json FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.job_id = %s AND j.org_id = %s ORDER BY jv.version DESC LIMIT 1",
            [target_job_id, security.org_id]
        )
        if job_row and job_row[0]:
            job_requirements = job_row[0]
            if isinstance(job_requirements, str):
                try:
                    job_requirements = json.loads(job_requirements)
                except json.JSONDecodeError:
                    job_requirements = {}

    job_skills_list = (job_requirements.get("must_have_skills") or []) + (job_requirements.get("nice_to_have_skills") or [])
    hard_skills_score = semantic_skill_match_score(profile.get("skills", []), job_skills_list, profile.get("domains", []))
    soft_skills_score = compute_soft_skills_score(profile, job_requirements)

    experience_score = compute_experience_score(profile, job_requirements)

    domain_score = compute_domain_score(profile, job_requirements)

    name_lower = (profile.get("name") or "").lower()

    # Generate (and cache) an LLM summary of the CV for the candidate profile page.
    if data.get("status") != "processing":
        try:
            ensure_cv_summary(database, candidate_id, profile)
        except Exception:
            logger.exception("Failed to generate CV summary for %s", candidate_id)

    scores = {
        "hard_skills": hard_skills_score,
        "soft_skills": soft_skills_score,
        "experience": experience_score,
        "domain_knowledge": domain_score
    }

    return CandidateDetailResponse(
        candidate_id=candidate_id,
        profile=profile,
        scores=scores,
        evidence={},
        questions=profile.get("interview_questions", []),
        status=data.get("status", "processing"),
    )


class CandidateListResponse(BaseModel):
    candidates: List[Any]


@router.get("", response_model=CandidateListResponse)
def list_candidates(job_id: str, security: SecurityContext = Depends(get_security_context)) -> CandidateListResponse:
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    cands = candidate_repo.list_candidates(security.org_id, job_id=job_id)
    return CandidateListResponse(candidates=cands)


@router.delete("/{candidate_id}", status_code=200)
def delete_candidate(
    job_id: str,
    candidate_id: str,
    security: SecurityContext = Depends(get_security_context)
):
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    deleted = candidate_repo.delete_candidate(candidate_id, security.org_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "success", "deleted": candidate_id}


@router.delete("", status_code=200)
def clear_all_candidates(
    job_id: str,
    security: SecurityContext = Depends(get_security_context)
):
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    count = candidate_repo.clear_all_candidates(job_id, security.org_id)
    return {"status": "success", "deleted_count": count}


@router.post("/details/{candidate_id}/interviews", status_code=status.HTTP_202_ACCEPTED)
def generate_interview_questions(
    job_id: str,
    candidate_id: str,
    security: SecurityContext = Depends(get_security_context)
):
    database = get_database(settings.database_dsn)
    
    # Verify candidate belongs to org_id
    cand_row = database.fetchone("SELECT id FROM candidates WHERE id = %s AND org_id = %s", [candidate_id, security.org_id])
    if not cand_row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Update candidate status
    database.execute("UPDATE candidates SET status = 'interview' WHERE id = %s", [candidate_id])
    
    # Retrieve profile details
    row = database.fetchone(
        "SELECT id, profile_json FROM candidate_snapshots WHERE candidate_id = %s ORDER BY snapshot_version DESC LIMIT 1",
        [candidate_id]
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No snapshots found for candidate")
        
    snapshot_id, profile = row[0], row[1]
    if isinstance(profile, str): profile = json.loads(profile)
    
    # Fetch job requirements to determine gaps and pass context
    target_job_id = job_id
    try:
        uuid.UUID(target_job_id)
    except (ValueError, TypeError):
        # job_id might be "all" or invalid. Try extracting from profile.
        profile_job_id = profile.get("job_id") or profile.get("job_guid")
        if profile_job_id:
            try:
                uuid.UUID(profile_job_id)
                target_job_id = profile_job_id
            except (ValueError, TypeError):
                target_job_id = None
        else:
            target_job_id = None

    job_requirements = {}
    if target_job_id:
        job_row = database.fetchone(
            "SELECT parsed_json FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.job_id = %s AND j.org_id = %s ORDER BY jv.version DESC LIMIT 1",
            [target_job_id, security.org_id]
        )
        if job_row and job_row[0]:
            job_requirements = job_row[0]
            if isinstance(job_requirements, str):
                try:
                    job_requirements = json.loads(job_requirements)
                except json.JSONDecodeError:
                    job_requirements = {}

    must_have = job_requirements.get("must_have_skills") or []
    cand_skills = profile.get("skills") or []
    cand_skills_lower = {s.lower() for s in cand_skills}
    gaps = [s for s in must_have if s.lower() not in cand_skills_lower]

    # Generate questions using Groq/LLM
    llm_config = LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
    llm_client = LLMClient(llm_config)
    generator = InterviewGenerator(llm_client=llm_client)
    question_set = generator.generate(
        skills=profile.get("skills", []),
        candidate_snapshot_id=snapshot_id,
        gaps=gaps,
        roles=profile.get("roles", []),
        job_requirements=job_requirements,
        profile=profile
    )
    
    questions_list = [
        {
            "prompt": q.prompt,
            "category": q.category,
            "rationale": q.rationale,
            "target_skill": q.target_skill,
        }
        for q in question_set.questions
    ]
    
    # Save back to profile
    database.execute(
        "UPDATE candidate_snapshots SET profile_json = jsonb_set(profile_json, '{interview_questions}', %s::jsonb, true) WHERE id = %s",
        [json.dumps(questions_list), snapshot_id]
    )
    
    return {"status": "success", "questions_generated": len(questions_list), "questions": questions_list}


@router.get("/{candidate_id}/profile", response_model=CandidateJobProfileResponse)
def get_candidate_job_profile(
    job_id: str,
    candidate_id: str,
    security: SecurityContext = Depends(get_security_context)
) -> CandidateJobProfileResponse:
    from fastapi import HTTPException
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    
    # 1. Fetch Candidate
    data = candidate_repo.get_candidate(candidate_id, org_id=security.org_id)
    if not data:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    profile = data.get("profile", {})
    cand_name = profile.get("name", "Unknown Candidate")
    cand_status = data.get("status", "processing")
    
    # 2. Fetch Job Details
    job_row = database.fetchone(
        "SELECT jv.title, jv.parsed_json, jv.id FROM job_versions jv JOIN jobs j ON jv.job_id = j.id WHERE jv.job_id = %s AND j.org_id = %s ORDER BY jv.version DESC LIMIT 1",
        [job_id, security.org_id]
    )
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_title, parsed_json, job_version_id = job_row
    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except json.JSONDecodeError:
            parsed_json = {}
            
    # 3. Calculate matched & missing skills
    must_have = parsed_json.get("must_have_skills") or []
    nice_to_have = parsed_json.get("nice_to_have_skills") or []
    job_skills_list = must_have + nice_to_have
    
    cand_skills = profile.get("skills") or []
    
    matched_skills = []
    missing_skills = []
    
    # Match strictly against extracted skills/domains (no raw_text fallback) so the
    # matched/missing lists reflect what parsing actually extracted and stay consistent
    # with the Hard Skills score.
    for js in job_skills_list:
        if check_candidate_has_requirement(js, cand_skills, profile.get("domains") or []):
            matched_skills.append(js)
        else:
            missing_skills.append(js)
            
    # 4. Fetch/calculate fit evaluation
    run_row = database.fetchone(
        """
        SELECT o.final_score, o.explanation_text 
        FROM ranking_run_outputs o
        JOIN ranking_runs r ON o.ranking_run_id = r.id
        JOIN candidate_snapshots s ON o.candidate_snapshot_id = s.id
        WHERE r.job_version_id = %s AND s.candidate_id = %s
        ORDER BY r.created_at DESC LIMIT 1
        """,
        [job_version_id, candidate_id]
    )
    
    if run_row:
        fit_score = float(run_row[0])
        has_run = True
    else:
        # Dynamically compute a fallback score
        hard_skills_score = semantic_skill_match_score(cand_skills, job_skills_list, profile.get("domains", []))
        soft_skills_score = compute_soft_skills_score(profile, parsed_json)
        experience_score = compute_experience_score(profile, parsed_json)
        domain_score = compute_domain_score(profile, parsed_json)

        if hard_skills_score < 15.0:
            experience_score_gated = 0.0
            domain_score_gated = 0.0
        else:
            experience_score_gated = experience_score
            domain_score_gated = domain_score

        fit_score = 0.4 * hard_skills_score + 0.15 * experience_score_gated + 0.1 * domain_score_gated + 0.35 * soft_skills_score
        has_run = False

    # Classify fit level
    if fit_score >= 75:
        fit_level = "Good Fit"
    elif fit_score >= 50:
        fit_level = "Medium Fit"
    elif fit_score >= 35:
        fit_level = "Bad Fit"
    else:
        fit_level = "No Fit"
        
    try:
        years_exp = int(profile.get("years_experience") or 0)
    except:
        years_exp = 0

    # Build a clean, candidate-facing fit summary from structured signals (avoids
    # surfacing the raw internal ranking explanation, which leaks decision/score artefacts).
    first_name = (cand_name or "This candidate").split(" ")[0]
    expl_parts = [f"{first_name} is a {fit_level.lower()} for {job_title}, with an overall match of {fit_score:.0f}%."]
    if matched_skills:
        expl_parts.append(f"Strengths align with the role on {', '.join(matched_skills[:5])}.")
    if missing_skills:
        expl_parts.append(f"Worth probing in the interview: {', '.join(missing_skills[:4])}.")
    if years_exp:
        expl_parts.append(f"Brings {years_exp} year{'s' if years_exp != 1 else ''} of experience.")
    if not has_run:
        expl_parts.append("Run the AI Ranking Pipeline for a full scored breakdown.")
    fit_explanation = " ".join(expl_parts)

    # 5. Semantic relevance: summarise the CV and the job, then explain how the two
    #    relate. Each artefact is cached so repeat opens of the modal are cheap.
    cv_summary = ""
    job_summary = parsed_json.get("summary") or ""
    semantic_summary = ""
    semantic_relevant = False
    try:
        from services.summaries.generator import SummaryService
        summarizer = SummaryService(_build_llm())

        cv_summary = ensure_cv_summary(database, candidate_id, profile)

        if not job_summary:
            job_summary, job_used_llm = summarizer.summarize_job(parsed_json, "")
            parsed_json["summary"] = job_summary
            if job_used_llm:
                database.execute(
                    "UPDATE job_versions SET parsed_json = %s WHERE id = %s",
                    [json.dumps(parsed_json), str(job_version_id)],
                )

        cached_rel = profile.get("semantic_summary") or ""
        if cached_rel:
            semantic_summary = cached_rel
            semantic_relevant = bool(profile.get("semantic_relevant", False))
        else:
            rel = summarizer.relevance(cv_summary, job_summary)
            semantic_summary = rel.get("summary", "")
            semantic_relevant = bool(rel.get("relevant", False))
            # Only cache real LLM relevance, so fallbacks self-heal next load.
            if rel.get("used_llm"):
                _update_latest_snapshot(database, candidate_id, {
                    "semantic_summary": semantic_summary,
                    "semantic_relevant": semantic_relevant,
                })
    except Exception:
        logger.exception("Failed to generate semantic relevance for %s", candidate_id)

    return CandidateJobProfileResponse(
        candidate_id=candidate_id,
        candidate_name=cand_name,
        job_title=job_title,
        status=cand_status,
        years_experience=years_exp,
        education_level=profile.get("education_level") or "Not Specified",
        certifications=profile.get("certifications") or [],
        career_trajectory=profile.get("career_trajectory") or "Not Specified",
        domains=profile.get("domains") or [],
        soft_skills=profile.get("soft_skills") or [],
        skills=cand_skills,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        fit_score=fit_score,
        fit_level=fit_level,
        fit_explanation=fit_explanation,
        cv_summary=cv_summary,
        job_summary=job_summary,
        semantic_summary=semantic_summary,
        semantic_relevant=semantic_relevant,
    )
