from fastapi import APIRouter, status

from schemas.jobs import JobCreateRequest, JobCreateResponse
from pydantic import BaseModel
from typing import List, Any
from core.config import settings
from core.database import get_database
from services.events.repository import EventRepository
from services.jobs.repository import JobRepository
from services.workers.event_factory import build_event
from services.workers.factory import build_producer
from services.workers.kafka_topics import JOB_CREATED

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest) -> JobCreateResponse:
    database = get_database(settings.database_dsn)
    job_repo = JobRepository(database)
    event_repo = EventRepository(database)
    producer = build_producer(settings.broker_list())

    job = job_repo.create_job(
        org_id="11111111-1111-1111-1111-111111111111",
        created_by="22222222-2222-2222-2222-222222222222",
        title=payload.title,
        raw_text=payload.raw_text,
    )
    from services.jobs.parser import JobDescriptionParser
    from services.llm.client import LLMClient
    import json
    import dataclasses

    llm = LLMClient(api_key=settings.llm_api_key)
    parser = JobDescriptionParser(llm)
    parsed_jd = parser.parse(payload.raw_text)
    
    # Update job to active and save the parsed structured JSON to the job_versions table
    database.execute("UPDATE jobs SET status = 'active' WHERE id = %s", [job.job_id])
    database.execute("UPDATE job_versions SET parsed_json = %s WHERE id = %s", [json.dumps(dataclasses.asdict(parsed_jd)), job.job_version_id])

    event_repo.append(
        org_id="11111111-1111-1111-1111-111111111111",
        event_type="JOB_CREATED",
        aggregate_type="job",
        aggregate_id=job.job_id,
        payload={"job_id": job.job_id, "job_version_id": job.job_version_id},
    )
    event = build_event(
        event_type="JobCreated",
        org_id="11111111-1111-1111-1111-111111111111",
        payload={"job_id": job.job_id, "job_version_id": job.job_version_id, "created_by": "22222222-2222-2222-2222-222222222222"},
    )
    producer.publish(JOB_CREATED, event)
    return JobCreateResponse(job_id=job.job_id, status="active")

class JobListResponse(BaseModel):
    jobs: List[Any]

@router.get("", response_model=JobListResponse)
def list_jobs() -> JobListResponse:
    database = get_database(settings.database_dsn)
    job_repo = JobRepository(database)
    jobs = job_repo.list_jobs("11111111-1111-1111-1111-111111111111")
    return JobListResponse(jobs=jobs)
