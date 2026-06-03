"""Feature store for reading and writing candidate/job features.

Provides an in-memory implementation for tests and a PostgreSQL
implementation that correctly handles the feature_definitions FK
relationship required by the schema.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class FeatureRecord:
    entity_id: str
    feature_name: str
    value: float
    evidence: Dict[str, object]


class FeatureStore:
    def write(self, records: Iterable[FeatureRecord], model_version: str = "v0") -> None:
        raise NotImplementedError

    def read_for_entity(self, entity_id: str) -> List[FeatureRecord]:
        raise NotImplementedError


class InMemoryFeatureStore(FeatureStore):
    def __init__(self) -> None:
        self._data: Dict[str, List[FeatureRecord]] = {}

    def write(self, records: Iterable[FeatureRecord], model_version: str = "v0") -> None:
        for record in records:
            self._data.setdefault(record.entity_id, []).append(record)

    def read_for_entity(self, entity_id: str) -> List[FeatureRecord]:
        return list(self._data.get(entity_id, []))


class PostgresFeatureStore(FeatureStore):
    """Feature store backed by PostgreSQL.

    Handles the feature_definitions lookup/upsert and writes to
    candidate_features with proper FK references.
    """

    def __init__(self, db: "Database") -> None:
        from apps.api.src.core.database import Database

        self._db: Database = db
        self._feature_cache: Dict[str, str] = {}

    def _ensure_feature_definition(self, name: str, feature_type: str = "extracted") -> str:
        """Get or create a feature_definition row and return its id."""
        if name in self._feature_cache:
            return self._feature_cache[name]

        if not self._db.is_configured:
            fid = str(uuid.uuid4())
            self._feature_cache[name] = fid
            return fid

        row = self._db.fetchone(
            "SELECT id FROM feature_definitions WHERE name = %s",
            [name],
        )
        if row:
            fid = str(row[0])
        else:
            fid = str(uuid.uuid4())
            self._db.execute(
                "INSERT INTO feature_definitions (id, name, feature_type) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO NOTHING",
                [fid, name, feature_type],
            )
            # Re-read in case of race condition
            row = self._db.fetchone("SELECT id FROM feature_definitions WHERE name = %s", [name])
            if row:
                fid = str(row[0])

        self._feature_cache[name] = fid
        return fid

    def write(self, records: Iterable[FeatureRecord], model_version: str = "v0") -> None:
        if not self._db.is_configured:
            return None
        for record in records:
            feature_id = self._ensure_feature_definition(record.feature_name)
            self._db.execute(
                "INSERT INTO candidate_features "
                "(id, candidate_snapshot_id, feature_id, value_json, evidence_json, model_version) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    record.entity_id,
                    feature_id,
                    json.dumps({"value": record.value}),
                    json.dumps(record.evidence),
                    model_version,
                ],
            )

    def read_for_entity(self, entity_id: str) -> List[FeatureRecord]:
        """Read all features for a candidate snapshot."""
        if not self._db.is_configured:
            return []
        rows = self._db.fetchall(
            "SELECT fd.name, cf.value_json, cf.evidence_json "
            "FROM candidate_features cf "
            "JOIN feature_definitions fd ON fd.id = cf.feature_id "
            "WHERE cf.candidate_snapshot_id = %s",
            [entity_id],
        )
        results = []
        for row in rows:
            name = row[0]
            value_json = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            evidence_json = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            results.append(FeatureRecord(
                entity_id=entity_id,
                feature_name=name,
                value=float(value_json.get("value", 0.0)),
                evidence=evidence_json,
            ))
        return results
