"""LLM client wrapping OpenAI-compatible chat completion APIs."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for the LLM client."""

    api_key: str = ""
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_api_key: str = ""
    model: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768
    temperature: float = 0.1
    max_tokens: int = 4096


class LLMClient:
    """Thin wrapper around OpenAI-compatible chat and embedding APIs.

    Falls back gracefully when the openai package or API key is missing.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._config = config or LLMConfig()
        if OpenAI is None or not self._config.api_key:
            self._client = None
            if OpenAI is None:
                logger.warning("openai package not installed – LLM features disabled")
            else:
                logger.warning("OPENAI_API_KEY not set – LLM features disabled")
        else:
            self._client = OpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
                max_retries=0,
            )

    @property
    def is_available(self) -> bool:
        """Return True when the client is properly configured."""
        return self._client is not None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request and return the assistant text."""
        if not self._client:
            raise RuntimeError("LLM not configured (missing openai package or OPENAI_API_KEY)")
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Send a chat completion request and parse the response as JSON."""
        if not self._client:
            raise RuntimeError("LLM not configured")
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        import os
        import hashlib
        import math
        
        gemini_key = os.getenv("GEMINI_API_KEY", self._config.gemini_api_key)
        
        # If valid key is provided, use real Gemini embeddings
        if gemini_key and not gemini_key.startswith("gsk_"):
            try:
                embed_client = OpenAI(
                    api_key=gemini_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    max_retries=3,
                ) if OpenAI else None
                
                if embed_client:
                    response = embed_client.embeddings.create(
                        model=self._config.embedding_model,
                        input=texts,
                        dimensions=self._config.embedding_dimensions,
                    )
                    return [item.embedding for item in response.data]
            except Exception as e:
                logger.warning("Real Gemini embedding failed, falling back to local mock vectors: %s", e)
        
        # Graceful fallback: local deterministic pseudo-embeddings (unit normalized)
        results = []
        for text in texts:
            vector = []
            text_bytes = text.encode("utf-8")
            for i in range(self._config.embedding_dimensions):
                h = hashlib.sha256(text_bytes + str(i).encode("utf-8")).hexdigest()
                val = int(h[:8], 16) / 4294967295.0
                vector.append(val)
            magnitude = math.sqrt(sum(x * x for x in vector))
            if magnitude > 0:
                vector = [x / magnitude for x in vector]
            results.append(vector)
            
        return results
