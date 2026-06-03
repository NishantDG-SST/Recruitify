"""Tailored interview question generator.

Uses an LLM to produce candidate-specific questions that probe claimed skills,
explore identified gaps, and verify career narrative.  Falls back to template-
based questions when the LLM is unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

INTERVIEW_SYSTEM_PROMPT = """\
You are a senior technical recruiter preparing interview questions.
Given a candidate's profile and the job requirements, generate targeted
interview questions.  Return a JSON object:

{
  "questions": [
    {
      "question": "the question text",
      "category": "skill_verification | gap_probing | culture_fit | career_narrative | technical_depth",
      "rationale": "why this question matters for this specific candidate",
      "target_skill": "the skill or gap this question probes"
    }
  ]
}

Rules:
- Generate 5–8 questions total.
- At least 2 must probe specific gaps or weaknesses.
- At least 1 must verify a claimed skill with a concrete scenario.
- At least 1 must explore career trajectory decisions.
- Questions must reference specific details from the candidate's profile.
- Return ONLY valid JSON, no markdown fences."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InterviewQuestion:
    """A single tailored interview question."""

    prompt: str
    category: str = "general"
    rationale: str = ""
    target_skill: str = ""


@dataclass(frozen=True)
class InterviewQuestionSet:
    """Complete set of interview questions for a candidate."""

    candidate_snapshot_id: str
    questions: List[InterviewQuestion]
    generation_method: str = "template"


# ---------------------------------------------------------------------------
# Template-based fallback
# ---------------------------------------------------------------------------

_SKILL_TEMPLATES = [
    "Describe a challenging project where you used {skill}. What was your specific contribution?",
    "What is a common pitfall when working with {skill}, and how have you handled it?",
]

_GAP_TEMPLATES = [
    "This role requires {skill}. While it doesn't appear prominently in your background, "
    "do you have any related experience?",
    "How would you approach ramping up on {skill} if selected for this role?",
]

_TRAJECTORY_TEMPLATES = [
    "Walk me through the decision to move from {prev_role} to {current_role}.",
    "Where do you see your career heading in the next 2-3 years?",
]

_GENERAL_TEMPLATES = [
    "Tell me about a time you had to learn a new technology under a tight deadline.",
    "Describe a situation where you disagreed with a technical decision. How did you handle it?",
]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class InterviewGenerator:
    """Generate tailored interview questions for shortlisted candidates."""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self._llm = llm_client

    def generate(
        self,
        skills: List[str],
        candidate_snapshot_id: str = "",
        gaps: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        job_requirements: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
    ) -> InterviewQuestionSet:
        """Generate interview questions for a candidate."""
        if self._llm is not None and self._llm.is_available and profile:
            return self._generate_llm(
                candidate_snapshot_id=candidate_snapshot_id,
                profile=profile,
                job_requirements=job_requirements,
            )
        return self._generate_templates(
            candidate_snapshot_id=candidate_snapshot_id,
            skills=skills,
            gaps=gaps or [],
            roles=roles or [],
        )

    # ------------------------------------------------------------------
    # LLM generation
    # ------------------------------------------------------------------

    def _generate_llm(
        self,
        candidate_snapshot_id: str,
        profile: Dict[str, Any],
        job_requirements: Optional[Dict[str, Any]],
    ) -> InterviewQuestionSet:
        user_prompt_parts = [f"## Candidate Profile\n{_format_profile(profile)}"]
        if job_requirements:
            user_prompt_parts.append(f"\n## Job Requirements\n{_format_profile(job_requirements)}")

        try:
            raw = self._llm.complete_json(INTERVIEW_SYSTEM_PROMPT, "\n".join(user_prompt_parts))
        except Exception:
            logger.exception("LLM interview generation failed – using templates")
            return self._generate_templates(
                candidate_snapshot_id=candidate_snapshot_id,
                skills=profile.get("skills", []),
                gaps=profile.get("gaps", []),
                roles=profile.get("roles", []),
            )

        questions = []
        for item in raw.get("questions", []):
            questions.append(InterviewQuestion(
                prompt=item.get("question", ""),
                category=item.get("category", "general"),
                rationale=item.get("rationale", ""),
                target_skill=item.get("target_skill", ""),
            ))

        return InterviewQuestionSet(
            candidate_snapshot_id=candidate_snapshot_id,
            questions=questions,
            generation_method="llm",
        )

    # ------------------------------------------------------------------
    # Template fallback
    # ------------------------------------------------------------------

    def _generate_templates(
        self,
        candidate_snapshot_id: str,
        skills: List[str],
        gaps: List[str],
        roles: List[str],
    ) -> InterviewQuestionSet:
        questions: List[InterviewQuestion] = []

        # Skill verification questions
        for skill in skills[:3]:
            for template in _SKILL_TEMPLATES[:1]:
                questions.append(InterviewQuestion(
                    prompt=template.format(skill=skill),
                    category="skill_verification",
                    target_skill=skill,
                ))

        # Gap probing questions
        for gap in gaps[:2]:
            questions.append(InterviewQuestion(
                prompt=_GAP_TEMPLATES[0].format(skill=gap),
                category="gap_probing",
                target_skill=gap,
            ))

        # Career trajectory
        if len(roles) >= 2:
            questions.append(InterviewQuestion(
                prompt=_TRAJECTORY_TEMPLATES[0].format(
                    prev_role=roles[-2] if len(roles) >= 2 else "your previous role",
                    current_role=roles[-1] if roles else "your current role",
                ),
                category="career_narrative",
            ))

        # General questions to fill up to 5 minimum
        for template in _GENERAL_TEMPLATES:
            if len(questions) >= 6:
                break
            questions.append(InterviewQuestion(prompt=template, category="culture_fit"))

        return InterviewQuestionSet(
            candidate_snapshot_id=candidate_snapshot_id,
            questions=questions,
            generation_method="template",
        )


def _format_profile(data: Dict[str, Any]) -> str:
    """Format a dict into readable bullet points for the LLM prompt."""
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)
