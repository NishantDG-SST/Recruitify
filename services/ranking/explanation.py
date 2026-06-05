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
You are given the job's requirements, the candidate's profile, and the raw scoring data (including their Rank and Name).
Your goal is to write a short, clear, and objective explanation (2-3 paragraphs max) of why 
this candidate was ranked as they were.

Follow these rules based on the candidate's Rank:
1. For Rank 1 to 10 (Top tier):
   - Lead with their strengths (e.g., expertise, high-scale experience, team leadership).
   - Frame minor gaps as constructive areas to explore in the interview.
   - Use positive framing.
   - The word "rejected" MUST NEVER appear in the explanation for these top candidates.
2. For Rank 11 to 20 (Middle tier):
   - Use neutral language noting both their strengths and gaps.
3. For Rank 21+ (Bottom tier):
   - Use objective, gap-focused language. If they missed key must-have requirements, state that clearly.
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
        rank: int = 0,
        candidate_name: str = "",
    ) -> str:
        """Generate a human-readable explanation of a ranking decision."""
        if not self._llm.is_available:
            return self._generate_fallback(score, decision, triggers, candidate_features, job_features, rank, candidate_name)
            
        user_prompt = self._build_user_prompt(
            job_features, candidate_features, score, decision, triggers, rank, candidate_name
        )

        try:
            explanation = self._llm.complete(EXPLANATION_SYSTEM_PROMPT, user_prompt)
            return explanation.strip()
        except Exception:
            logger.exception("LLM explanation generation failed")
            return self._generate_fallback(score, decision, triggers, candidate_features, job_features, rank, candidate_name)

    def _build_user_prompt(
        self,
        job_features: Dict[str, Any],
        candidate_features: Dict[str, Any],
        score: float,
        decision: str,
        triggers: List[str],
        rank: int = 0,
        candidate_name: str = "",
    ) -> str:
        """Build the structured prompt providing context to the LLM."""
        prompt = [
            f"## Ranking Decision",
            f"- Candidate Name: {candidate_name}",
            f"- Rank: {rank}",
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

    def _generate_fallback(
        self,
        score: float,
        decision: str,
        triggers: List[str],
        candidate_features: Dict[str, Any],
        job_features: Dict[str, Any],
        rank: int = 0,
        candidate_name: str = "",
    ) -> str:
        """Generate a basic template-based explanation when LLM is unavailable."""
        skills_score = candidate_features.get("skills", 1.0) * 100.0
        exp_score = candidate_features.get("experience", 1.0) * 100.0
        
        missing = []
        for k, v in candidate_features.items():
            if k not in ["skills", "experience", "education", "semantic_similarity"] and v == 0.0:
                missing.append(k)
                
        explanation = []
        name_str = candidate_name if candidate_name else "The candidate"
        
        if rank > 0 and rank <= 10:
            explanation.append(
                f"{name_str} is a top-ranked candidate (Rank #{rank}) with a strong score of {score:.1f}/100."
            )
            if exp_score >= 70:
                explanation.append(f"They bring solid relevant experience to the role.")
            if missing:
                explanation.append(f"Potential areas to explore in the interview include: {', '.join(missing)}.")
        elif rank > 0 and rank <= 20:
            explanation.append(
                f"{name_str} shows a solid alignment (Rank #{rank}) with a score of {score:.1f}/100."
            )
            if missing:
                explanation.append(f"They meet several requirements but have minor gaps in: {', '.join(missing)}.")
        else:
            if decision == "reject":
                if "must_have_failed" in triggers and missing:
                    explanation.append(
                        f"Candidate failed to meet key must-have requirements: {', '.join(missing)}."
                    )
                else:
                    explanation.append(
                        f"Candidate did not meet the required score threshold for this position."
                    )
            else:
                explanation.append(
                    f"Candidate was shortlisted with a score of {score:.1f}/100."
                )
            if missing:
                explanation.append(f"Gaps identified in: {', '.join(missing)}.")
            
        explanation.append(
            f"Their skills alignment is {skills_score:.1f}/100 and experience alignment is {exp_score:.1f}/100."
        )
        
        return " ".join(explanation)
