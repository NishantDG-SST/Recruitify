import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from apps.api.src.core.database import Database

@dataclass
class EmbeddingModelDef:
    id: str
    name: str
    version: str
    provider: str
    embedding_dim: int

@dataclass
class RankingModelDef:
    id: str
    name: str
    version: str
    algorithm: str

@dataclass
class PromptVersionDef:
    id: str
    template_name: str
    version: str
    template_text: str

class ModelRegistry:
    """Manages versioned ML models and LLM prompts."""

    def __init__(self, db: Database):
        self._db = db

    def get_embedding_model(self, name: str, version: str) -> Optional[EmbeddingModelDef]:
        if not self._db.is_configured:
            return None
            
        row = self._db.fetchone(
            "SELECT id, name, version, provider, embedding_dim FROM embedding_models WHERE name = %s AND version = %s",
            [name, version]
        )
        if not row:
            return None
        return EmbeddingModelDef(*row)

    def register_embedding_model(self, name: str, version: str, provider: str, dim: int) -> EmbeddingModelDef:
        if not self._db.is_configured:
            return EmbeddingModelDef("dummy", name, version, provider, dim)
            
        # Upsert logic
        self._db.execute(
            """INSERT INTO embedding_models (name, version, provider, embedding_dim) 
               VALUES (%s, %s, %s, %s) ON CONFLICT (name, version) DO NOTHING""",
            [name, version, provider, dim]
        )
        return self.get_embedding_model(name, version)

    def get_prompt_version(self, template_name: str, version: str) -> Optional[PromptVersionDef]:
        if not self._db.is_configured:
            return None
            
        row = self._db.fetchone(
            """SELECT pv.id, pt.name, pv.version, pv.template_text 
               FROM prompt_versions pv 
               JOIN prompt_templates pt ON pv.prompt_template_id = pt.id 
               WHERE pt.name = %s AND pv.version = %s""",
            [template_name, version]
        )
        if not row:
            return None
        return PromptVersionDef(*row)
