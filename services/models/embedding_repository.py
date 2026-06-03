from dataclasses import dataclass
from typing import List

from apps.api.src.core.database import Database


@dataclass(frozen=True)
class EmbeddingRecord:
    candidate_snapshot_id: str
    embedding_model_id: str
    vector: List[float]


class EmbeddingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def write(self, record: EmbeddingRecord) -> None:
        if not self._db.is_configured:
            return None
            
        # Ensure the model exists in the database and get its UUID
        model_row = self._db.fetchone(
            "SELECT id FROM embedding_models WHERE name = %s AND version = %s",
            [record.embedding_model_id, "latest"]
        )
        if model_row:
            model_id = model_row[0]
        else:
            self._db.execute(
                "INSERT INTO embedding_models (name, version, provider, embedding_dim) VALUES (%s, %s, %s, %s)",
                [record.embedding_model_id, "latest", "gemini", len(record.vector)]
            )
            model_row = self._db.fetchone(
                "SELECT id FROM embedding_models WHERE name = %s AND version = %s",
                [record.embedding_model_id, "latest"]
            )
            model_id = model_row[0]

        self._db.execute(
            "INSERT INTO candidate_embeddings (candidate_snapshot_id, embedding_model_id, embedding) "
            "VALUES (%s, %s, %s)",
            [record.candidate_snapshot_id, model_id, record.vector],
        )
