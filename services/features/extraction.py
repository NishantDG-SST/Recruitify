"""Feature extraction service using LLM with keyword fallback.

When an LLM client is available the service sends the resume text through a
structured extraction prompt and parses the JSON response.  When the client
is unavailable it falls back to regex/keyword heuristics so that the pipeline
still functions (with lower quality) without an API key.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.taxonomy.normalizer import TaxonomyNormalizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are a resume analysis engine.  Extract structured candidate information
from the resume text provided.  Return a JSON object with exactly these keys:

{
  "name": "<candidate full name>",
  "current_role": "<candidate's most recent or current role>",
  "technical_skills": ["list of technical skills, tools, languages, frameworks"],
  "soft_skills": ["list of soft skills like leadership, communication"],
  "roles": ["list of job titles the candidate has held"],
  "domains": ["list of industry domains or sectors"],
  "years_experience": <integer – total years of professional experience>,
  "education_level": "<high_school | bachelors | masters | phd | unknown>",
  "certifications": ["list of certifications mentioned"],
  "career_trajectory": "<ascending | lateral | mixed | early_career>"
}

Rules:
- Only include skills and roles clearly evidenced in the text.
- Normalise skill names to their most common form (e.g. 'JS' → 'javascript').
- years_experience should be your best integer estimate; use 0 if unclear.
- Return ONLY valid JSON, no markdown fences."""

# ---------------------------------------------------------------------------
# Keyword / regex fallback patterns
# ---------------------------------------------------------------------------

_TECH_KEYWORDS: set[str] = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "ruby", "php", "scala", "kotlin", "swift", "sql", "nosql",
    "react", "angular", "vue", "node", "express", "django", "flask", "fastapi",
    "spring", "rails", "nextjs", "next.js",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "kafka", "rabbitmq", "graphql", "rest", "grpc",
    "git", "ci/cd", "jenkins", "github", "gitlab",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "spark",
    "linux", "bash", "powershell",
    "m&a", "fema", "sebi", "rbi", "due diligence", "compliance", "restructuring",
    "corporate governance", "fundraising", "strategic investments"
}

_SOFT_KEYWORDS: set[str] = {
    "leadership", "communication", "teamwork", "mentoring", "collaboration",
    "problem-solving", "analytical", "critical thinking", "agile", "scrum",
    "project management", "stakeholder management", "presentation",
}

_DOMAIN_KEYWORDS: set[str] = {
    "fintech", "healthcare", "e-commerce", "saas", "edtech", "adtech",
    "cybersecurity", "logistics", "media", "gaming", "banking", "insurance",
    "telecom", "energy", "automotive", "retail", "travel",
}

_EDUCATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bph\.?d\b", re.IGNORECASE), "phd"),
    (re.compile(r"\bdoctorate\b", re.IGNORECASE), "phd"),
    (re.compile(r"\bmasters?\b", re.IGNORECASE), "masters"),
    (re.compile(r"\bmba\b", re.IGNORECASE), "masters"),
    (re.compile(r"(?:^|\s)m\.?\s?s\.?c?\.?(?:\s|,|$)", re.IGNORECASE), "masters"),
    (re.compile(r"(?:^|\s)m\.?\s?tech\b", re.IGNORECASE), "masters"),
    (re.compile(r"\bbachelors?\b", re.IGNORECASE), "bachelors"),
    (re.compile(r"(?:^|\s)b\.?\s?s\.?c?\.?(?:\s|,|$)", re.IGNORECASE), "bachelors"),
    (re.compile(r"(?:^|\s)b\.?\s?tech\b", re.IGNORECASE), "bachelors"),
    (re.compile(r"(?:^|\s)b\.?\s?a\.?(?:\s|,|$)", re.IGNORECASE), "bachelors"),
]

_YEARS_PATTERN = re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience)?", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionResult:
    """Structured candidate profile extracted from resume text."""

    name: str = ""
    current_role: str = ""
    skills: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    years_experience: int = 0
    education_level: str = "unknown"
    certifications: List[str] = field(default_factory=list)
    career_trajectory: str = "unknown"
    extraction_method: str = "keyword"
    raw_extraction: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ExtractionService:
    """Extract structured features from resume text.

    Uses an LLM when available, otherwise falls back to keyword matching.
    All skills are normalised through the taxonomy normalizer.
    """

    def __init__(
        self,
        normalizer: Optional[TaxonomyNormalizer] = None,
        llm_client: Optional[Any] = None,
    ) -> None:
        self._normalizer = normalizer or TaxonomyNormalizer()
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> ExtractionResult:
        """Extract features from *text*, using LLM when possible."""
        if self._llm is not None and self._llm.is_available:
            return self._extract_llm(text)
        return self._extract_keywords(text)

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    def _extract_llm(self, text: str) -> ExtractionResult:
        try:
            raw = self._llm.complete_json(EXTRACTION_SYSTEM_PROMPT, text[:12_000])
        except Exception:
            logger.exception("LLM extraction failed – falling back to keywords")
            return self._extract_keywords(text)

        tech = [s.strip().lower() for s in raw.get("technical_skills", [])]
        soft = [s.strip().lower() for s in raw.get("soft_skills", [])]
        normalized = self._normalizer.normalize_skills(tech)

        return ExtractionResult(
            name=raw.get("name", "Unknown Candidate"),
            current_role=raw.get("current_role", "Unknown Role"),
            skills=normalized.skills,
            soft_skills=soft,
            roles=[r.strip() for r in raw.get("roles", [])],
            domains=[d.strip().lower() for d in raw.get("domains", [])],
            years_experience=int(raw.get("years_experience", 0)),
            education_level=raw.get("education_level", "unknown"),
            certifications=[c.strip() for c in raw.get("certifications", [])],
            career_trajectory=raw.get("career_trajectory", "unknown"),
            extraction_method="llm",
            raw_extraction=raw,
        )

    # ------------------------------------------------------------------
    # Keyword / regex fallback
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> ExtractionResult:
        lower = text.lower()
        tokens = set(re.findall(r"[\w.+#/-]+", lower))

        tech = sorted({t for t in tokens if t in _TECH_KEYWORDS})
        soft_set = {s for s in _SOFT_KEYWORDS if s in lower}
        
        # Soft skill inference patterns (Issue 4)
        soft_inference_mappings = {
            "leadership": ["led team", "managed team", "team lead", "head of", "director of", "vp of", "chief", "founded", "built team"],
            "communication": ["presented", "communicated", "stakeholder", "client-facing", "cross-functional", "wrote documentation"],
            "mentoring": ["mentored", "coached", "trained", "onboarded", "junior developers", "interns"],
            "collaboration": ["collaborated", "worked closely", "partnered with", "cross-team", "cross-functional"],
            "teamwork": ["team of", "collaborated", "worked with", "alongside", "cross-functional"],
            "problem-solving": ["solved", "debugged", "troubleshoot", "root cause", "resolved", "optimized"],
            "project management": ["managed project", "delivered project", "project plan", "roadmap", "milestone", "sprint"],
            "stakeholder management": ["strong communication", "stakeholder", "executive", "c-suite", "board", "client relationship"],
            "analytical": ["analyzed", "data-driven", "metrics", "analytics", "insights"],
            "critical thinking": ["evaluated", "assessed", "strategic", "analysis"],
            "agile": ["agile", "scrum", "kanban", "sprint", "standup"],
            "presentation": ["presented", "presentation", "demo", "conference", "spoke at"],
        }
        
        for skill, patterns in soft_inference_mappings.items():
            for pattern in patterns:
                if pattern in lower:
                    soft_set.add(skill)
                    break
                    
        soft = sorted(list(soft_set))
        domains = sorted({d for d in _DOMAIN_KEYWORDS if d in lower})

        normalized = self._normalizer.normalize_skills(tech)

        edu = "unknown"
        # Check patterns in priority order (phd > masters > bachelors)
        for pattern, level in _EDUCATION_PATTERNS:
            if pattern.search(text):
                edu = level
                break

        years = 0
        years_match = _YEARS_PATTERN.search(text)
        if years_match:
            years = int(years_match.group(1))

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        name = "Unknown Candidate"
        current_role = "Unknown Role"
        
        if lines:
            name = lines[0]
            if len(name) > 60:
                name = name[:60]
        if len(lines) > 1:
            current_role = lines[1]
            if len(current_role) > 60:
                current_role = current_role[:60]

        return ExtractionResult(
            name=name,
            current_role=current_role,
            skills=normalized.skills,
            soft_skills=soft,
            roles=[],
            domains=domains,
            years_experience=years,
            education_level=edu,
            certifications=[],
            career_trajectory="unknown",
            extraction_method="keyword",
            raw_extraction={},
        )
