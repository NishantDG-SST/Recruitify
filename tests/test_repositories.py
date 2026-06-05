import os

import pytest

from core.database import get_database
from services.candidates.repository import CandidateRepository
from services.events.repository import EventRepository
from services.jobs.repository import JobRepository
from services.ranking.repository import RankingOutputRecord, RankingRepository


@pytest.mark.skipif(not os.getenv("DATABASE_DSN"), reason="DATABASE_DSN not set")
def test_job_and_event_repositories() -> None:
    db = get_database(os.getenv("DATABASE_DSN"))
    job_repo = JobRepository(db)
    event_repo = EventRepository(db)

    job = job_repo.create_job(
        org_id="00000000-0000-0000-0000-000000000001",
        created_by="00000000-0000-0000-0000-000000000002",
        title="Backend Engineer",
        raw_text="Python and Postgres",
    )

    record = event_repo.append(
        org_id="00000000-0000-0000-0000-000000000001",
        event_type="JOB_CREATED",
        aggregate_type="job",
        aggregate_id=job.job_id,
        payload={"job_id": job.job_id},
    )

    assert job.job_id
    assert job.job_version_id
    assert record.event_id


@pytest.mark.skipif(not os.getenv("DATABASE_DSN"), reason="DATABASE_DSN not set")
def test_candidate_and_ranking_repositories() -> None:
    db = get_database(os.getenv("DATABASE_DSN"))
    candidate_repo = CandidateRepository(db)
    ranking_repo = RankingRepository(db)
    job_repo = JobRepository(db)

    job = job_repo.create_job(
        org_id="00000000-0000-0000-0000-000000000001",
        created_by="00000000-0000-0000-0000-000000000002",
        title="Platform Engineer",
        raw_text="Go and Kubernetes",
    )

    snapshot = candidate_repo.create_snapshot(
        org_id="00000000-0000-0000-0000-000000000001",
        profile_json={"skills": ["python"]},
        resume_document_id=None,
    )

    run = ranking_repo.create_run(
        org_id="00000000-0000-0000-0000-000000000001",
        job_version_id=job.job_version_id,
        scoring_version="v0",
    )

    ranking_repo.write_outputs(
        [
            RankingOutputRecord(
                run_id=run.run_id,
                candidate_snapshot_id=snapshot.candidate_snapshot_id,
                final_score=83.5,
                rank=1,
                decision="shortlist",
            )
        ]
    )

    outputs = ranking_repo.list_outputs(run.run_id)
    assert outputs
    assert outputs[0].candidate_snapshot_id == snapshot.candidate_snapshot_id
