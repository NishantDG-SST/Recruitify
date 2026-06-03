from dataclasses import dataclass
from typing import Iterable, List

from apps.api.src.core.database import Database


@dataclass(frozen=True)
class RankingRunRecord:
    run_id: str


@dataclass(frozen=True)
class RankingOutputRecord:
    run_id: str
    candidate_snapshot_id: str
    final_score: float
    rank: int
    decision: str
    explanation_text: str = ""


class RankingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_run(self, org_id: str, job_version_id: str, scoring_version: str) -> RankingRunRecord:
        run_id = job_version_id
        if self._db.is_configured:
            self._db.execute(
                "INSERT INTO ranking_runs (id, org_id, job_version_id, status, scoring_version) VALUES (%s, %s, %s, %s, %s)",
                [run_id, org_id, job_version_id, "completed", scoring_version],
            )
        return RankingRunRecord(run_id=run_id)

    def write_outputs(self, outputs: Iterable[RankingOutputRecord]) -> None:
        if not self._db.is_configured:
            return None
        for output in outputs:
            self._db.execute(
                "INSERT INTO ranking_run_outputs (ranking_run_id, candidate_snapshot_id, final_score, rank, decision, explanation_text) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    output.run_id,
                    output.candidate_snapshot_id,
                    output.final_score,
                    output.rank,
                    output.decision,
                    output.explanation_text,
                ],
            )

    def write_feature_contributions(self, run_id: str, candidate_id: str, contributions: dict[str, float]) -> None:
        if not self._db.is_configured:
            return None
        for feature_name, value in contributions.items():
            # In a real app we'd look up the feature_id. For now we mock it or rely on feature_definitions.
            # Assuming a DB helper or direct query:
            row = self._db.fetchone("SELECT id FROM feature_definitions WHERE name = %s", [feature_name])
            if row:
                feature_id = row[0]
                self._db.execute(
                    "INSERT INTO feature_contributions (ranking_run_id, candidate_snapshot_id, feature_id, contribution) "
                    "VALUES (%s, %s, %s, %s)",
                    [run_id, candidate_id, feature_id, value]
                )

    def write_override(self, run_id: str, candidate_id: str, old_rank: int, new_rank: int, reason: str, user_id: str = None) -> None:
        if not self._db.is_configured:
            return None
        self._db.execute(
            "INSERT INTO ranking_overrides (ranking_run_id, candidate_snapshot_id, old_rank, new_rank, reason, user_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [run_id, candidate_id, old_rank, new_rank, reason, user_id]
        )

    def list_outputs(self, run_id: str) -> List[RankingOutputRecord]:
        if not self._db.is_configured:
            return []
        rows = self._db.fetchall(
            "SELECT candidate_snapshot_id, final_score, rank, decision, explanation_text FROM ranking_run_outputs WHERE ranking_run_id = %s",
            [run_id],
        )
        if not rows:
            return []
        return [
            RankingOutputRecord(
                run_id=run_id,
                candidate_snapshot_id=row[0],
                final_score=float(row[1]),
                rank=int(row[2]),
                decision=row[3],
                explanation_text=row[4] if row[4] else "",
            )
            for row in rows
        ]
