"""Batch embedding helper that delegates to EmbeddingService.

Handles chunking for large batches and collects results.
"""

from dataclasses import dataclass
from typing import Iterable, List

from services.models.embedding_service import EmbeddingResult, EmbeddingService


@dataclass(frozen=True)
class BatchEmbeddingResult:
    model_id: str
    vectors: List[List[float]]


class EmbeddingBatcher:
    """Batch-embed a collection of texts with configurable chunk size."""

    def __init__(self, service: EmbeddingService, chunk_size: int = 64) -> None:
        self._service = service
        self._chunk_size = chunk_size

    def embed_batch(self, texts: Iterable[str]) -> BatchEmbeddingResult:
        """Embed all *texts*, batching API calls in chunks of *chunk_size*."""
        text_list = list(texts)
        if not text_list:
            return BatchEmbeddingResult(model_id="", vectors=[])

        all_vectors: List[List[float]] = []
        model_id = ""

        for start in range(0, len(text_list), self._chunk_size):
            chunk = text_list[start : start + self._chunk_size]
            results = self._service.embed_batch(chunk)
            for result in results:
                model_id = result.model_id
                all_vectors.append(result.vector)

        return BatchEmbeddingResult(model_id=model_id, vectors=all_vectors)
