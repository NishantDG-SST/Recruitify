"""Job Description parser using LLM.

Extracts structured requirements (hard skills, soft skills, experience level, 
domain knowledge, must-have vs nice-to-have) from raw job description text.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.llm.client import LLMClient
from services.taxonomy.normalizer import TaxonomyNormalizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

JD_PARSER_SYSTEM_PROMPT = """\
You are an expert technical recruiter analyzing a job description.
Extract structured job requirements from the provided text.
Return a JSON object with exactly these keys:

{
  "title": "<cleaned job title>",
  "must_have_skills": ["list of absolutely required technical skills, tools, languages"],
  "nice_to_have_skills": ["list of preferred/bonus technical skills"],
  "soft_skills": ["list of required soft skills (e.g., leadership, communication)"],
  "domains": ["list of industry domains or sectors mentioned"],
  "years_experience_min": <integer – minimum years of experience required, use 0 if not specified>,
  "education_level": "<high_school | bachelors | masters | phd | unknown>",
  "certifications": ["list of required or preferred certifications"]
}

Rules:
- Normalise skill names to their most common form (e.g. 'JS' -> 'javascript').
- Only include requirements explicitly stated in the text.
- If education is not specified, use 'unknown'.
- Return ONLY valid JSON, no markdown fences."""

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedJobDescription:
    """Structured requirements extracted from a job description."""

    title: str
    must_have_skills: List[str]
    nice_to_have_skills: List[str]
    soft_skills: List[str]
    domains: List[str]
    years_experience_min: int = 0
    education_level: str = "unknown"
    certifications: List[str] = field(default_factory=list)
    raw_extraction: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class JobDescriptionParser:
    """Extract structured requirements from raw JD text using an LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        normalizer: Optional[TaxonomyNormalizer] = None,
    ) -> None:
        self._llm = llm_client
        self._normalizer = normalizer or TaxonomyNormalizer()

    def parse(self, text: str) -> ParsedJobDescription:
        """Parse raw JD text into structured requirements."""
        if not self._llm.is_available:
            logger.warning("LLM not available – returning empty JD parse")
            return self._empty_fallback(text)
            
        try:
            raw = self._llm.complete_json(JD_PARSER_SYSTEM_PROMPT, text[:15_000])
        except Exception:
            logger.exception("LLM JD parsing failed")
            return self._empty_fallback(text)
            
        must_have = [s.strip().lower() for s in raw.get("must_have_skills", [])]
        nice_to_have = [s.strip().lower() for s in raw.get("nice_to_have_skills", [])]
        soft = [s.strip().lower() for s in raw.get("soft_skills", [])]
        
        normalized_must = self._normalizer.normalize_skills(must_have)
        normalized_nice = self._normalizer.normalize_skills(nice_to_have)

        return ParsedJobDescription(
            title=raw.get("title", "Unknown Role").strip(),
            must_have_skills=normalized_must.skills,
            nice_to_have_skills=normalized_nice.skills,
            soft_skills=soft,
            domains=[d.strip().lower() for d in raw.get("domains", [])],
            years_experience_min=int(raw.get("years_experience_min", 0)),
            education_level=raw.get("education_level", "unknown"),
            certifications=[c.strip() for c in raw.get("certifications", [])],
            raw_extraction=raw,
        )

    def _empty_fallback(self, text: str) -> ParsedJobDescription:
        """Return a basic fallback when LLM is unavailable."""
        title = text.split("\n")[0][:100].strip() if text else "Unknown Role"
        return ParsedJobDescription(
            title=title,
            must_have_skills=[],
            nice_to_have_skills=[],
            soft_skills=[],
            domains=[],
            raw_extraction={},
        )
