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
    embedding_model: str = "gemini-embedding-001"
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
        
        import time
        import random
        
        models = [self._config.model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        seen = set()
        model_rotation = [x for x in models if not (x in seen or seen.add(x))]
        
        last_exception = None
        for attempt, model in enumerate(model_rotation):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_exception = e
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "too many requests" in err_str
                is_server_error = "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str
                
                if (is_rate_limit or is_server_error) and attempt < len(model_rotation) - 1:
                    logger.warning(f"LLM call failed with {model}. Rotating model to {model_rotation[attempt+1]}...")
                    continue
                else:
                    break
                    
        if last_exception:
            backoff = 2.0
            for attempt in range(3):
                try:
                    response = self._client.chat.completions.create(
                        model=model_rotation[-1],
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=self._config.temperature,
                        max_tokens=self._config.max_tokens,
                    )
                    return response.choices[0].message.content or ""
                except Exception as e:
                    last_exception = e
                    err_str = str(e).lower()
                    is_rate_limit = "429" in err_str or "rate limit" in err_str or "too many requests" in err_str
                    is_server_error = "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str
                    
                    if (is_rate_limit or is_server_error) and attempt < 2:
                        sleep_time = backoff * (2 ** attempt) + random.uniform(0.1, 0.5)
                        logger.warning(f"Model rotation exhausted. Retrying with {model_rotation[-1]} in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                    else:
                        break
                        
        raise last_exception

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Send a chat completion request and parse the response as JSON.

        ``max_tokens`` overrides the configured cap for this call — keep it small for
        short structured outputs (providers count the reservation against the TPM limit).
        """
        if not self._client:
            raise RuntimeError("LLM not configured")

        import time
        import random

        eff_max = max_tokens if max_tokens is not None else self._config.max_tokens
        models = [self._config.model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        seen = set()
        model_rotation = [x for x in models if not (x in seen or seen.add(x))]
        
        last_exception = None
        for attempt, model in enumerate(model_rotation):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self._config.temperature,
                    max_tokens=eff_max,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or "{}"
                return json.loads(raw)
            except Exception as e:
                last_exception = e
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "too many requests" in err_str
                is_server_error = "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str
                
                if (is_rate_limit or is_server_error) and attempt < len(model_rotation) - 1:
                    logger.warning(f"LLM JSON call failed with {model}. Rotating model to {model_rotation[attempt+1]}...")
                    continue
                else:
                    break
                    
        if last_exception:
            backoff = 2.0
            for attempt in range(3):
                try:
                    response = self._client.chat.completions.create(
                        model=model_rotation[-1],
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=self._config.temperature,
                        max_tokens=eff_max,
                        response_format={"type": "json_object"},
                    )
                    raw = response.choices[0].message.content or "{}"
                    return json.loads(raw)
                except Exception as e:
                    last_exception = e
                    err_str = str(e).lower()
                    is_rate_limit = "429" in err_str or "rate limit" in err_str or "too many requests" in err_str
                    is_server_error = "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str
                    
                    if (is_rate_limit or is_server_error) and attempt < 2:
                        sleep_time = backoff * (2 ** attempt) + random.uniform(0.1, 0.5)
                        logger.warning(f"Model rotation exhausted. Retrying with {model_rotation[-1]} in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                    else:
                        break
                        
        raise last_exception

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        import os
        import hashlib
        import math
        
        gemini_key = os.getenv("GEMINI_API_KEY", self._config.gemini_api_key)
        dims = self._config.embedding_dimensions
        model = self._config.embedding_model

        # If a valid Gemini key is provided, use real Gemini embeddings via the
        # native batchEmbedContents endpoint (the OpenAI-compat path / older
        # text-embedding-004 model are no longer available).
        if gemini_key and not gemini_key.startswith("gsk_"):
            try:
                import httpx

                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:batchEmbedContents?key={gemini_key}"
                )
                payload = {
                    "requests": [
                        {
                            "model": f"models/{model}",
                            "content": {"parts": [{"text": t or " "}]},
                            "outputDimensionality": dims,
                        }
                        for t in texts
                    ]
                }
                resp = httpx.post(url, json=payload, timeout=30.0)
                resp.raise_for_status()
                embeddings = resp.json().get("embeddings", [])
                if len(embeddings) == len(texts):
                    out: list[list[float]] = []
                    for item in embeddings:
                        v = item.get("values", [])
                        # Normalize to unit length (recommended for <3072-dim Gemini embeddings, and required for stable cosine).
                        mag = math.sqrt(sum(x * x for x in v)) or 1.0
                        out.append([x / mag for x in v])
                    return out
                logger.warning("Gemini embedding returned %d vectors for %d inputs; falling back", len(embeddings), len(texts))
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
