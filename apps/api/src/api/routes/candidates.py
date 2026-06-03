import uuid
import json
import time
import logging
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, status
from typing import List, Any
from pydantic import BaseModel

from schemas.candidates import CandidateDetailResponse, CandidateUploadResponse
from core.config import settings
from core.database import get_database
from services.candidates.repository import CandidateRepository
from services.documents.parser import DocumentParser
from services.documents.service import DocumentService
from services.documents.storage_local import LocalDocumentStorage, LocalStorageConfig
from services.events.repository import EventRepository
from services.features.extraction import ExtractionService
from services.llm.client import LLMClient, LLMConfig
from services.taxonomy.normalizer import TaxonomyNormalizer

router = APIRouter(prefix="/jobs/{job_id}/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


@router.post("", response_model=CandidateUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_candidates(job_id: str, files: list[UploadFile] = File(...)) -> CandidateUploadResponse:
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

    for upload in files:
        content = upload.file.read()
        result = service.ingest(content, upload.filename or "resume", upload.content_type or "")

        # 1. Create snapshot with raw text
        snapshot = candidate_repo.create_snapshot(
            org_id="11111111-1111-1111-1111-111111111111",
            profile_json={"raw_text": result.parsed.text, "warnings": result.parsed.warnings, "job_id": job_id},
            resume_document_id=result.stored.document_id,
        )

        # 2. Extract features synchronously via LLM
        try:
            extracted = extractor.extract(result.parsed.text)
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
                [json.dumps(features), snapshot.candidate_snapshot_id]
            )
            # Mark candidate as extracted
            database.execute(
                "UPDATE candidates SET status = 'extracted' WHERE id = %s",
                [snapshot.candidate_id]
            )
            logger.info("Extracted %s -> %s", upload.filename, extracted.name)
            # Throttle to avoid Groq rate limits
            time.sleep(2)
        except Exception as e:
            logger.warning("Extraction failed for %s, will retry via worker: %s", upload.filename, e)

        # 3. Log event
        event_repo.append(
            org_id="11111111-1111-1111-1111-111111111111",
            event_type="RESUME_UPLOADED",
            aggregate_type="candidate",
            aggregate_id=snapshot.candidate_id,
            payload={
                "candidate_id": snapshot.candidate_id,
                "candidate_snapshot_id": snapshot.candidate_snapshot_id,
                "job_id": job_id,
                "document_id": result.stored.document_id,
            },
        )

    return CandidateUploadResponse(batch_id=batch_id)


@router.get("/details/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate_detail(job_id: str, candidate_id: str) -> CandidateDetailResponse:
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    data = candidate_repo.get_candidate(candidate_id)

    return CandidateDetailResponse(
        candidate_id=candidate_id,
        profile=data.get("profile", {}),
        scores={},
        evidence={},
        questions=data.get("profile", {}).get("interview_questions", []),
        status=data.get("status", "processing"),
    )

class CandidateListResponse(BaseModel):
    candidates: List[Any]

@router.get("", response_model=CandidateListResponse)
def list_candidates(job_id: str) -> CandidateListResponse:
    database = get_database(settings.database_dsn)
    candidate_repo = CandidateRepository(database)
    cands = candidate_repo.list_candidates("11111111-1111-1111-1111-111111111111", job_id=job_id)
    return CandidateListResponse(candidates=cands)

import json
from services.interviews.generator import InterviewGenerator

@router.post("/details/{candidate_id}/interviews", status_code=status.HTTP_202_ACCEPTED)
def generate_interview_questions(job_id: str, candidate_id: str):
    database = get_database(settings.database_dsn)
    
    # Update candidate status
    database.execute("UPDATE candidates SET status = 'interview' WHERE id = %s", [candidate_id])
    
    # Fetch snapshot features
    row = database.fetchone(
        "SELECT id, profile_json FROM candidate_snapshots WHERE candidate_id = %s ORDER BY snapshot_version DESC LIMIT 1",
        [candidate_id]
    )
    if not row:
        return {"status": "error", "message": "No snapshot found"}
        
    snapshot_id, profile = row[0], row[1]
    if isinstance(profile, str): profile = json.loads(profile)
    
    # Generate questions using Groq/LLM
    generator = InterviewGenerator()
    question_set = generator.generate(
        skills=profile.get("skills", []),
        candidate_snapshot_id=snapshot_id,
        gaps=[],
        roles=profile.get("roles", []),
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
