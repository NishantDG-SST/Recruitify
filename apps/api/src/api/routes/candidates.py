import uuid
import json
import time
import logging
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, status, Depends
from typing import List, Any
from pydantic import BaseModel

from schemas.candidates import CandidateDetailResponse, CandidateUploadResponse
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
)

router = APIRouter(prefix="/jobs/{job_id}/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


@router.post("", response_model=CandidateUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_candidates(
    job_id: str,
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

    # Build the LLM extractor for synchronous parsing
    llm_config = LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
    llm = LLMClient(llm_config)
    normalizer = TaxonomyNormalizer()
    extractor = ExtractionService(normalizer=normalizer, llm_client=llm)

    def _is_rate_limit(exc: Exception) -> bool:
        """Return True if the exception looks like a Groq/OpenAI 429."""
        msg = str(exc).lower()
        return "429" in msg or "rate limit" in msg or "rate_limit" in msg or "too many requests" in msg

    def _get_fallback_name(text: str, filename: str) -> str:
        import re
        # 1. Try to extract name from filename (e.g., "01_arjun_sharma_senior_ml.txt" -> "Arjun Sharma")
        name_parts = []
        base = filename.rsplit('.', 1)[0]
        # Split by underscores, hyphens, or spaces
        parts = [p.strip() for p in re.split(r'[_ -]', base) if p.strip()]
        for p in parts:
            if p.isdigit():
                continue
            # Skip common descriptive words in filename (like senior, ml, fullstack, devops, mid, weak, etc.)
            if p.lower() in {
                "senior", "junior", "ml", "fullstack", "devops", "mid", "weak", "weak2",
                "resume", "cv", "career", "change", "strong", "intern", "backend",
                "frontend", "ds", "pm", "analyst", "sre", "product", "data"
            }:
                break
            name_parts.append(p.capitalize())
        if name_parts:
            return " ".join(name_parts)
        
        # 2. Try first non-empty line from text
        if text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines and len(lines[0]) < 50:
                return lines[0]
                
        return "Unknown Candidate"

    def _try_extract(text: str, filename: str, max_retries: int = 3):
        """Attempt LLM extraction with retries. Returns (success, ExtractionResult or None)."""
        last_extracted = None
        last_err = None
        for attempt in range(max_retries):
            try:
                candidate_extracted = extractor.extract(text)
                last_extracted = candidate_extracted
                # Validate completeness
                has_role = bool(candidate_extracted.current_role and candidate_extracted.current_role.strip())
                has_skills = bool(candidate_extracted.skills)
                if not has_role:
                    raise RuntimeError(
                        f"Partial parse for {filename}: "
                        f"name='{candidate_extracted.name}' current_role is empty "
                        f"(skills={'present' if has_skills else 'also empty'})"
                    )
                return True, candidate_extracted
            except Exception as e:
                last_err = e
                if attempt == max_retries - 1:
                    logger.error(
                        "All %d LLM extraction attempts failed for %s (%s).",
                        max_retries, filename, last_err
                    )
                else:
                    if _is_rate_limit(e):
                        wait = 15 if attempt == 0 else 30
                        logger.warning(
                            "Rate limit hit for %s (attempt %d/%d) – backing off %ds",
                            filename, attempt + 1, max_retries, wait
                        )
                    else:
                        wait = 5 if attempt == 0 else 10
                        logger.warning(
                            "Extraction attempt %d/%d failed for %s (%s) – retrying in %ds",
                            attempt + 1, max_retries, filename, str(e), wait
                        )
                    time.sleep(wait)
        return False, last_extracted

    def _save_extracted(extracted, snapshot, result, upload_filename: str):
        """Persist extracted features and embeddings to DB."""
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
        database.execute(
            "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb WHERE id = %s",
            [json.dumps(features), snapshot.candidate_snapshot_id]
        )
        database.execute(
            "UPDATE candidates SET status = 'extracted' WHERE id = %s",
            [snapshot.candidate_id]
        )
        logger.info("Extracted %s -> %s", upload_filename, extracted.name)

        # Generate and write candidate embeddings synchronously
        from services.models.embedding_repository import EmbeddingRepository, EmbeddingRecord
        try:
            skills_text = ", ".join(extracted.skills)
            roles_text = ", ".join(extracted.roles)
            embed_input = f"Skills: {skills_text}\nRoles: {roles_text}\n\n{result.parsed.text}".strip()
            if not embed_input:
                embed_input = "empty resume"

            vectors = llm.embed([embed_input])
            if vectors:
                EmbeddingRepository(database).write(
                    EmbeddingRecord(
                        candidate_snapshot_id=snapshot.candidate_snapshot_id,
                        embedding_model_id=settings.embedding_model,
                        vector=vectors[0]
                    )
                )
                logger.info("Generated and persisted embedding for candidate snapshot %s", snapshot.candidate_snapshot_id)
        except Exception as emb_err:
            logger.warning("Embedding generation failed for %s: %s", upload_filename, emb_err)

    def _save_failed(partial, snapshot, result, upload_filename: str):
        """Persist failed extraction to DB with partial data (at least name) and status = 'failed'."""
        name = "Unknown Candidate"
        current_role = None
        skills = []
        soft_skills = []
        roles = []
        domains = []
        years_experience = 0
        education_level = None
        certifications = []
        career_trajectory = ""
        extraction_method = "failed"

        if partial is not None:
            if getattr(partial, "name", None):
                name = partial.name
            if getattr(partial, "current_role", None):
                current_role = partial.current_role
            if getattr(partial, "skills", None):
                skills = partial.skills
            if getattr(partial, "soft_skills", None):
                soft_skills = partial.soft_skills
            if getattr(partial, "roles", None):
                roles = partial.roles
            if getattr(partial, "domains", None):
                domains = partial.domains
            if getattr(partial, "years_experience", None):
                years_experience = partial.years_experience
            if getattr(partial, "education_level", None):
                education_level = partial.education_level
            if getattr(partial, "certifications", None):
                certifications = partial.certifications
            if getattr(partial, "career_trajectory", None):
                career_trajectory = partial.career_trajectory
            if getattr(partial, "extraction_method", None):
                extraction_method = partial.extraction_method

        # If name is still the default or empty, use fallback from filename/text
        if not name or name == "Unknown Candidate":
            name = _get_fallback_name(result.parsed.text, upload_filename)

        features = {
            "name": name,
            "current_role": current_role,
            "skills": skills,
            "soft_skills": soft_skills,
            "roles": roles,
            "domains": domains,
            "years_experience": years_experience,
            "education_level": education_level,
            "certifications": certifications,
            "career_trajectory": career_trajectory,
            "extraction_method": extraction_method,
        }

        database.execute(
            "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb WHERE id = %s",
            [json.dumps(features), snapshot.candidate_snapshot_id]
        )
        database.execute(
            "UPDATE candidates SET status = 'failed' WHERE id = %s",
            [snapshot.candidate_id]
        )
        logger.info("Saved failed extraction %s -> %s", upload_filename, name)

    # ---- First pass: process all CVs ----
    failed_items = []  # list of (filename, result, snapshot, partial) for retry

    for upload in files:
        content = upload.file.read()
        result = service.ingest(content, upload.filename or "resume", upload.content_type or "")

        # 1. Create snapshot with raw text
        snapshot = candidate_repo.create_snapshot(
            org_id=security.org_id,
            profile_json={"raw_text": result.parsed.text, "warnings": result.parsed.warnings, "job_id": job_id},
            resume_document_id=result.stored.document_id,
        )

        # 2. Extract features synchronously via LLM
        success, extracted_or_partial = _try_extract(result.parsed.text, upload.filename or "resume")

        if success:
            try:
                _save_extracted(extracted_or_partial, snapshot, result, upload.filename or "resume")
            except Exception as e:
                logger.warning("Post-extraction DB write failed for %s: %s", upload.filename, e)
        else:
            logger.warning(
                "First-pass extraction failed for %s – will retry after batch completes.",
                upload.filename
            )
            failed_items.append((upload.filename or "resume", result, snapshot, extracted_or_partial))

        # Throttle between CVs to avoid Groq rate limits (5s gap)
        time.sleep(5)

        # 3. Log event
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

    # ---- Retry pass: re-attempt any CVs that failed extraction ----
    if failed_items:
        logger.info(
            "Retry pass: %d CVs failed first-pass extraction. "
            "Waiting 30s for rate-limit window to recover...",
            len(failed_items)
        )
        time.sleep(30)

        for filename, result, snapshot, first_pass_partial in failed_items:
            success, extracted_or_partial = _try_extract(result.parsed.text, filename, max_retries=3)
            latest_partial = extracted_or_partial if extracted_or_partial is not None else first_pass_partial
            
            if success:
                try:
                    _save_extracted(extracted_or_partial, snapshot, result, filename)
                    logger.info("Retry pass succeeded for %s", filename)
                except Exception as e:
                    logger.warning("Retry pass DB write failed for %s: %s", filename, e)
            else:
                logger.error(
                    "Retry pass also failed for %s – saving candidate details with failed status.",
                    filename
                )
                try:
                    _save_failed(latest_partial, snapshot, result, filename)
                except Exception as e:
                    logger.error("Failed to save failed extraction state for %s: %s", filename, e)
            # Throttle between retries too
            time.sleep(5)

    return CandidateUploadResponse(batch_id=batch_id)


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
    hard_skills_score = semantic_skill_match_score(profile.get("skills", []), job_skills_list)
    soft_skills_score = compute_soft_skills_score(profile, job_requirements)

    experience_score = compute_experience_score(profile, job_requirements)

    domain_score = compute_domain_score(profile, job_requirements)

    name_lower = (profile.get("name") or "").lower()

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
    
    return {"status": "success", "questions_generated": len(questions_list)}
