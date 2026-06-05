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

    def get_candidate(self, candidate_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        if not self._db.is_configured:
            return {}
        
        query = """
            SELECT c.id, c.status, c.created_at, s.profile_json
            FROM candidates c
            LEFT JOIN (
                SELECT candidate_id, profile_json,
                       ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY snapshot_version DESC) as rn
                FROM candidate_snapshots
            ) s ON c.id = s.candidate_id AND s.rn = 1
            WHERE c.id = %s
        """
        params = [candidate_id]
        if org_id:
            query += " AND c.org_id = %s"
            params.append(org_id)
            
        row = self._db.fetchone(query, params)

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

    def delete_candidate(self, candidate_id: str, org_id: str) -> bool:
        """Delete a candidate and all related records across tables."""
        if not self._db.is_configured:
            return False

        # Verify ownership
        row = self._db.fetchone("SELECT id FROM candidates WHERE id = %s AND org_id = %s", [candidate_id, org_id])
        if not row:
            return False

        # Get snapshot IDs for cascade (needed for tables that FK on snapshot)
        snap_rows = self._db.fetchall("SELECT id FROM candidate_snapshots WHERE candidate_id = %s", [candidate_id])
        snap_ids = [r[0] for r in snap_rows]

        if snap_ids:
            placeholders = ",".join(["%s"] * len(snap_ids))
            # Delete from tables referencing snapshot IDs
            self._db.execute(f"DELETE FROM candidate_embeddings WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM candidate_features WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM interview_questions WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM ranking_overrides WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM ranking_run_outputs WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM ranking_run_inputs WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)
            self._db.execute(f"DELETE FROM feature_contributions WHERE candidate_snapshot_id IN ({placeholders})", snap_ids)

        # Delete from tables referencing candidate_id directly
        self._db.execute("DELETE FROM interview_rounds WHERE candidate_id = %s", [candidate_id])
        self._db.execute("DELETE FROM candidate_pii WHERE candidate_id = %s", [candidate_id])
        self._db.execute("DELETE FROM candidate_snapshots WHERE candidate_id = %s", [candidate_id])
        self._db.execute("DELETE FROM candidates WHERE id = %s AND org_id = %s", [candidate_id, org_id])
        return True

    def clear_all_candidates(self, job_id: str, org_id: str) -> int:
        """Delete all candidates associated with a specific job."""
        if not self._db.is_configured:
            return 0

        # Find candidate IDs linked to this job
        rows = self._db.fetchall(
            """
            SELECT DISTINCT c.id
            FROM candidates c
            JOIN candidate_snapshots s ON c.id = s.candidate_id
            WHERE c.org_id = %s AND s.profile_json->>'job_id' = %s
            """,
            [org_id, job_id]
        )

        count = 0
        for r in rows:
            if self.delete_candidate(r[0], org_id):
                count += 1
        return count
