from fastapi import APIRouter, Depends, status

from schemas.jobs import JobCreateRequest, JobCreateResponse
from pydantic import BaseModel
from typing import List, Any
from core.config import settings
from core.database import get_database
from core.auth import SecurityContext, get_security_context
from services.events.repository import EventRepository
from services.jobs.repository import JobRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest, security: SecurityContext = Depends(get_security_context)) -> JobCreateResponse:
    database = get_database(settings.database_dsn)
    job_repo = JobRepository(database)
    event_repo = EventRepository(database)

    job = job_repo.create_job(
        org_id=security.org_id,
        created_by=security.user_id,
        title=payload.title,
        raw_text=payload.raw_text,
    )
    from services.jobs.parser import JobDescriptionParser
    from services.llm.client import LLMClient, LLMConfig
    import json
    import dataclasses

    llm = LLMClient(LLMConfig(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    ))
    parser = JobDescriptionParser(llm)
    parsed_jd = parser.parse(payload.raw_text)
    
    # Update job to active and save the parsed structured JSON to the job_versions table
    database.execute("UPDATE jobs SET status = 'active' WHERE id = %s", [job.job_id])
    database.execute("UPDATE job_versions SET parsed_json = %s WHERE id = %s", [json.dumps(dataclasses.asdict(parsed_jd)), job.job_version_id])

    event_repo.append(
        org_id=security.org_id,
        event_type="JOB_CREATED",
        aggregate_type="job",
        aggregate_id=job.job_id,
        payload={"job_id": job.job_id, "job_version_id": job.job_version_id},
    )
    return JobCreateResponse(job_id=job.job_id, status="active")


class JobListResponse(BaseModel):
    jobs: List[Any]


@router.get("", response_model=JobListResponse)
def list_jobs(security: SecurityContext = Depends(get_security_context)) -> JobListResponse:
    database = get_database(settings.database_dsn)
    job_repo = JobRepository(database)
    jobs = job_repo.list_jobs(security.org_id)
    return JobListResponse(jobs=jobs)


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
def delete_job(job_id: str, security: SecurityContext = Depends(get_security_context)):
    """Delete a job and all associated data (candidates, ranking runs, versions, documents)."""
    from fastapi import HTTPException
    from services.candidates.repository import CandidateRepository

    database = get_database(settings.database_dsn)

    # Verify job belongs to this org
    job_row = database.fetchone(
        "SELECT id FROM jobs WHERE id = %s AND org_id = %s", [job_id, security.org_id]
    )
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")

    # 1. Delete all candidates associated with this job (cascade via candidate repo)
    candidate_repo = CandidateRepository(database)
    candidate_rows = database.fetchall(
        """
        SELECT DISTINCT c.id
        FROM candidates c
        JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE c.org_id = %s AND s.profile_json->>'job_id' = %s
        """,
        [security.org_id, job_id]
    )
    for row in candidate_rows:
        candidate_repo.delete_candidate(row[0], security.org_id)

    # 2. Delete ranking run dependencies (in FK-safe order)
    # ranking_runs links via job_version_id, not job_id — resolve via job_versions first
    version_rows = database.fetchall(
        "SELECT id FROM job_versions WHERE job_id = %s", [job_id]
    )
    version_ids = [r[0] for r in version_rows]
    if version_ids:
        ver_placeholders = ",".join(["%s"] * len(version_ids))
        run_rows = database.fetchall(
            f"SELECT id FROM ranking_runs WHERE job_version_id IN ({ver_placeholders})", version_ids
        )
        run_ids = [r[0] for r in run_rows]
        if run_ids:
            placeholders = ",".join(["%s"] * len(run_ids))
            database.execute(f"DELETE FROM ranking_run_inputs WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM ranking_run_outputs WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM ranking_overrides WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM bias_analysis_results WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM interview_questions WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM ranking_features WHERE ranking_run_id IN ({placeholders})", run_ids)
            database.execute(f"DELETE FROM ranking_runs WHERE id IN ({placeholders})", run_ids)

    # 3. Delete job versions and job record
    database.execute("DELETE FROM job_versions WHERE job_id = %s", [job_id])
    database.execute("DELETE FROM documents WHERE job_id = %s", [job_id])
    database.execute("DELETE FROM jobs WHERE id = %s AND org_id = %s", [job_id, security.org_id])

    return {"status": "deleted", "job_id": job_id}
