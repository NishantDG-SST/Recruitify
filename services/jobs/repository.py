import uuid
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from apps.api.src.core.database import Database


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    job_version_id: str


class JobRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_job(self, org_id: str, created_by: Optional[str], title: Optional[str], raw_text: Optional[str]) -> JobRecord:
        job_id = str(uuid.uuid4())
        job_version_id = str(uuid.uuid4())

        if self._db.is_configured:
            self._db.execute(
                "INSERT INTO jobs (id, org_id, created_by, status) VALUES (%s, %s, %s, %s)",
                [job_id, org_id, created_by, "processing"],
            )
            self._db.execute(
                "INSERT INTO job_versions (id, job_id, version, title, raw_text) VALUES (%s, %s, %s, %s, %s)",
                [job_version_id, job_id, 1, title, raw_text],
            )

        return JobRecord(job_id=job_id, job_version_id=job_version_id)

    def list_jobs(self, org_id: str) -> List[Dict[str, Any]]:
        if not self._db.is_configured:
            return []
        
        # Fetch jobs and their latest title from job_versions
        rows = self._db.fetchall(
            """
            SELECT j.id, j.status, j.created_at, v.title
            FROM jobs j
            LEFT JOIN (
                SELECT job_id, title,
                       ROW_NUMBER() OVER(PARTITION BY job_id ORDER BY version DESC) as rn
                FROM job_versions
            ) v ON j.id = v.job_id AND v.rn = 1
            WHERE j.org_id = %s
            ORDER BY j.created_at DESC
            """,
            [org_id]
        )
        return [{"id": r[0], "status": r[1], "created_at": r[2], "title": r[3] or "Untitled Job"} for r in rows]
