"""LLM-powered explanation generation for ranking decisions.

Takes the candidate's profile, job requirements, and the raw scoring outputs,
and generates a transparent, human-readable explanation of why the candidate
received their score and decision.
"""

import logging
from typing import Any, Dict, List, Optional

from services.llm.client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

EXPLANATION_SYSTEM_PROMPT = """\
You are an expert technical recruiter explaining a ranking decision to a hiring manager.
You are given the job's requirements, the candidate's profile, and the raw scoring data.
Your goal is to write a short, clear, and objective explanation (2-3 paragraphs max) of why 
this candidate was ranked as they were.

Follow these rules:
- Be objective and evidence-based. Reference specific skills or gaps.
- Explain the 'why' behind the score, not just repeating the numbers.
- If the candidate failed a must-have requirement, state that clearly as the primary reason for rejection.
- If the candidate scored highly, highlight their strongest alignments with the job requirements.
- Use a professional, direct tone.
"""

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class RankingExplanationService:
    """Generate explanations for ranking decisions."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def generate(
        self,
        candidate_id: str,
        job_features: Dict[str, Any],
        candidate_features: Dict[str, Any],
        score: float,
        decision: str,
        triggers: List[str],
    ) -> str:
        """Generate a human-readable explanation of a ranking decision."""
        if not self._llm.is_available:
            return self._generate_fallback(score, decision, triggers)
            
        user_prompt = self._build_user_prompt(
            job_features, candidate_features, score, decision, triggers
        )

        try:
            explanation = self._llm.complete(EXPLANATION_SYSTEM_PROMPT, user_prompt)
            return explanation.strip()
        except Exception:
            logger.exception("LLM explanation generation failed")
            return self._generate_fallback(score, decision, triggers)

    def _build_user_prompt(
        self,
        job_features: Dict[str, Any],
        candidate_features: Dict[str, Any],
        score: float,
        decision: str,
        triggers: List[str],
    ) -> str:
        """Build the structured prompt providing context to the LLM."""
        prompt = [
            f"## Ranking Decision",
            f"- Decision: {decision.upper()}",
            f"- Final Score: {score:.1f}/100",
            f"- Triggers: {', '.join(triggers) if triggers else 'None'}",
            "",
            "## Job Requirements",
            self._format_dict(job_features),
            "",
            "## Candidate Profile",
            self._format_dict(candidate_features),
        ]
        return "\n".join(prompt)

    def _format_dict(self, data: Dict[str, Any]) -> str:
        """Format a dictionary into bullet points."""
        if not data:
            return "- None provided"
        return "\n".join(
            f"- {k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in data.items()
        )

    def _generate_fallback(self, score: float, decision: str, triggers: List[str]) -> str:
        """Generate a basic template-based explanation when LLM is unavailable."""
        if decision == "reject":
            if "must_have_failed" in triggers:
                return (
                    f"Candidate was rejected because they failed one or more must-have "
                    f"requirements. Their overall semantic alignment score was {score:.1f}."
                )
            return f"Candidate did not meet the required score threshold (scored {score:.1f})."
            
        return (
            f"Candidate was shortlisted with a strong score of {score:.1f}, indicating "
            f"good alignment with the core job requirements."
        )
