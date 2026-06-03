import uuid
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json

from apps.api.src.core.database import Database


@dataclass(frozen=True)
class CandidateSnapshotRecord:
    candidate_id: str
    candidate_snapshot_id: str


class CandidateRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_snapshot(
        self,
        org_id: str,
        profile_json: dict,
        resume_document_id: Optional[str],
    ) -> CandidateSnapshotRecord:
        candidate_id = str(uuid.uuid4())
        snapshot_id = str(uuid.uuid4())

        if self._db.is_configured:
            self._db.execute(
                "INSERT INTO candidates (id, org_id, status) VALUES (%s, %s, %s)",
                [candidate_id, org_id, "active"],
            )
            self._db.execute(
                "INSERT INTO candidate_snapshots (id, candidate_id, snapshot_version, source, profile_json, resume_document_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [snapshot_id, candidate_id, 1, "upload", json.dumps(profile_json), resume_document_id],
            )

        return CandidateSnapshotRecord(candidate_id=candidate_id, candidate_snapshot_id=snapshot_id)

    def list_candidates(self, org_id: str, job_id: str = None) -> List[Dict[str, Any]]:
        if not self._db.is_configured:
            return []
            
        if job_id and job_id != "all":
            query = """
            SELECT c.id, c.status, c.created_at, s.profile_json
            FROM candidates c
            LEFT JOIN (
                SELECT candidate_id, profile_json,
                       ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY snapshot_version DESC) as rn
                FROM candidate_snapshots
            ) s ON c.id = s.candidate_id AND s.rn = 1
            WHERE c.org_id = %s AND s.profile_json->>'job_id' = %s
            ORDER BY c.created_at DESC
            LIMIT 50
            """
            params = [org_id, job_id]
        else:
            query = """
            SELECT c.id, c.status, c.created_at, s.profile_json
            FROM candidates c
            LEFT JOIN (
                SELECT candidate_id, profile_json,
                       ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY snapshot_version DESC) as rn
                FROM candidate_snapshots
            ) s ON c.id = s.candidate_id AND s.rn = 1
            WHERE c.org_id = %s
            ORDER BY c.created_at DESC
            LIMIT 50
            """
            params = [org_id]
            
        rows = self._db.fetchall(query, params)
        
        candidates = []
        for r in rows:
            try:
                profile = r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}")
            except:
                profile = {}
                
            candidates.append({
                "id": r[0],
                "status": r[1],
                "created_at": r[2],
                "name": profile.get("name", "Unknown Candidate"),
                "role": profile.get("current_role", "Candidate")
            })
        return candidates

    def get_candidate(self, candidate_id: str) -> Dict[str, Any]:
        if not self._db.is_configured:
            return {}
        
        row = self._db.fetchone(
            """
            SELECT c.id, c.status, c.created_at, s.profile_json
            FROM candidates c
            LEFT JOIN (
                SELECT candidate_id, profile_json,
                       ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY snapshot_version DESC) as rn
                FROM candidate_snapshots
            ) s ON c.id = s.candidate_id AND s.rn = 1
            WHERE c.id = %s
            """,
            [candidate_id]
        )

        if not row:
            return {}

        try:
            profile = row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}")
        except:
            profile = {}
            
        return {
            "id": row[0],
            "status": row[1],
            "created_at": row[2],
            "profile": profile
        }
