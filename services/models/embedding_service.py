"""Embedding service with real LLM embeddings and a zero-vector fallback.

When an LLMClient is available, embeddings are generated via the OpenAI-
compatible embeddings API.  Otherwise a deterministic zero-vector stub is
returned so that downstream code can still function.
"""

import hashlib
import math
from dataclasses import dataclass
from typing import List, Optional

from services.llm.client import LLMClient


@dataclass(frozen=True)
class EmbeddingResult:
    model_id: str
    vector: List[float]


class EmbeddingService:
    """Generate text embeddings, using a real model when possible."""

    def __init__(
        self,
        model_id: str = "text-embedding-3-small",
        dim: int = 1024,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self._model_id = model_id
        self._dim = dim
        self._llm = llm_client

    @property
    def is_real(self) -> bool:
        """Return True when backed by an actual embedding model."""
        return self._llm is not None and self._llm.is_available

    def embed(self, text: str) -> EmbeddingResult:
        """Embed a single text string."""
        if self._llm is not None and self._llm.is_available:
            vectors = self._llm.embed([text])
            return EmbeddingResult(model_id=self._model_id, vector=vectors[0])
        return EmbeddingResult(model_id=self._model_id, vector=self._deterministic_stub(text))

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed a batch of texts in a single API call when possible."""
        if self._llm is not None and self._llm.is_available:
            vectors = self._llm.embed(texts)
            return [EmbeddingResult(model_id=self._model_id, vector=v) for v in vectors]
        return [
            EmbeddingResult(model_id=self._model_id, vector=self._deterministic_stub(t))
            for t in texts
        ]

    def _deterministic_stub(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-embedding from the text hash.

        This is NOT a real embedding — it exists only so that the pipeline
        can run end-to-end without an API key during development.
        """
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        raw = [int(digest[i : i + 2], 16) / 255.0 for i in range(0, min(len(digest), self._dim * 2), 2)]
        # Pad or truncate to dim
        raw = (raw * (self._dim // len(raw) + 1))[: self._dim]
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]
