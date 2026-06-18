"""LLM-backed summarization for candidates, jobs, and candidate↔job relevance.

Produces three artefacts:
  * CV summary       – a recruiter-facing prose summary of a parsed resume.
  * Job summary      – a recruiter-facing prose summary of a parsed job.
  * Semantic match   – a narrative tying a CV summary to a job summary, with a
                       boolean flag for whether the two are meaningfully relevant.

Every method degrades gracefully to a deterministic, template-based summary when
the LLM is unavailable, so callers always get usable text.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


CV_SYSTEM_PROMPT = """\
You are an expert technical recruiter. Write a concise, professional summary of a
candidate based on their parsed resume profile.

Rules:
- 3-4 sentences, plain prose (no markdown, no headings, no bullet points).
- Cover seniority, core technical strengths, domain experience, and any standout
  qualities (leadership, scale, trajectory).
- Be factual and specific to the data provided. Do NOT invent details."""

JOB_SYSTEM_PROMPT = """\
You are an expert technical recruiter. Write a concise, professional summary of a
job opening based on the parsed job requirements.

Rules:
- 3-4 sentences, plain prose (no markdown, no headings, no bullet points).
- Cover the role's seniority, the most important required skills, the
  domain/industry, and the kind of candidate who would excel.
- Be factual and specific to the data provided. Do NOT invent details."""

RELEVANCE_SYSTEM_PROMPT = """\
You are an expert technical recruiter assessing fit. You are given a CANDIDATE
SUMMARY and a JOB SUMMARY. Judge how semantically relevant the candidate's
background is to this specific job.

Return ONLY a valid JSON object (no markdown fences):
{
  "relevant": true | false,
  "summary": "2-3 sentence explanation of how the candidate's background fits this job."
}

Rules for the summary:
- Lead with the candidate's strengths and concrete overlaps (shared skills, domain, seniority).
- Meeting OR exceeding the required experience/seniority is a POSITIVE — never frame it as
  a concern or a drawback. More experience than required is a good thing.
- Only mention a gap if the candidate is genuinely MISSING a required skill, and phrase it
  neutrally as "an area to explore in the interview" — not as a reason against them.
- Do not invent gaps or add hedging ("however…") when the candidate is a strong match.
- Keep a positive, recruiter-facing tone.

Set "relevant" to true when there is meaningful overlap in skills, domain, or role.
Only set it to false when the candidate is from an unrelated discipline, and then briefly
explain why."""


def _join(values: Any) -> str:
    if isinstance(values, (list, tuple, set)):
        return ", ".join(str(v) for v in values if v)
    return str(values or "")


class SummaryService:
    """Generate prose summaries and relevance narratives via an LLM."""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self._llm = llm_client

    @property
    def _available(self) -> bool:
        return self._llm is not None and getattr(self._llm, "is_available", False)

    # ------------------------------------------------------------------
    # CV summary
    # ------------------------------------------------------------------

    def summarize_cv(self, profile: Dict[str, Any]) -> tuple[str, bool]:
        """Return (summary, used_llm). used_llm is False when a template fallback was used."""
        name = profile.get("name") or "The candidate"
        if self._available:
            user_prompt = (
                f"Candidate profile:\n"
                f"- Name: {name}\n"
                f"- Current role: {profile.get('current_role') or 'N/A'}\n"
                f"- Years of experience: {profile.get('years_experience') or 'N/A'}\n"
                f"- Career trajectory: {profile.get('career_trajectory') or 'N/A'}\n"
                f"- Education level: {profile.get('education_level') or 'N/A'}\n"
                f"- Skills: {_join(profile.get('skills'))}\n"
                f"- Soft skills: {_join(profile.get('soft_skills'))}\n"
                f"- Domains: {_join(profile.get('domains'))}\n"
                f"- Certifications: {_join(profile.get('certifications')) or 'None'}\n"
                f"- Past roles: {_join(profile.get('roles'))}\n"
            )
            try:
                text = self._llm.complete(CV_SYSTEM_PROMPT, user_prompt).strip()
                if text:
                    return text, True
            except Exception:
                logger.exception("LLM CV summary failed – using template fallback")
        return self._fallback_cv(profile), False

    def _fallback_cv(self, profile: Dict[str, Any]) -> str:
        name = profile.get("name") or "The candidate"
        role = profile.get("current_role") or "professional"
        yrs = profile.get("years_experience")
        skills = _join((profile.get("skills") or [])[:5])
        domains = _join(profile.get("domains"))
        parts = [f"{name} is a {role}"]
        if yrs:
            parts[0] += f" with {yrs} years of experience"
        parts[0] += "."
        if skills:
            parts.append(f"Core strengths include {skills}.")
        if domains:
            parts.append(f"Domain experience spans {domains}.")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Job summary
    # ------------------------------------------------------------------

    def summarize_job(self, parsed_json: Dict[str, Any], raw_text: str = "") -> tuple[str, bool]:
        """Return (summary, used_llm). used_llm is False when a template fallback was used."""
        title = parsed_json.get("title") or "This role"
        if self._available:
            user_prompt = (
                f"Job requirements:\n"
                f"- Title: {title}\n"
                f"- Must-have skills: {_join(parsed_json.get('must_have_skills'))}\n"
                f"- Nice-to-have skills: {_join(parsed_json.get('nice_to_have_skills'))}\n"
                f"- Domains: {_join(parsed_json.get('domains'))}\n"
                f"- Soft skills: {_join(parsed_json.get('soft_skills'))}\n"
                f"- Minimum years of experience: {parsed_json.get('years_experience_min', 'N/A')}\n"
                f"- Education level: {parsed_json.get('education_level') or 'N/A'}\n"
            )
            if raw_text:
                user_prompt += f"\nOriginal description (excerpt):\n{raw_text[:1500]}"
            try:
                text = self._llm.complete(JOB_SYSTEM_PROMPT, user_prompt).strip()
                if text:
                    return text, True
            except Exception:
                logger.exception("LLM job summary failed – using template fallback")
        return self._fallback_job(parsed_json), False

    def _fallback_job(self, parsed_json: Dict[str, Any]) -> str:
        title = parsed_json.get("title") or "This role"
        must = _join((parsed_json.get("must_have_skills") or [])[:6])
        domains = _join(parsed_json.get("domains"))
        parts = [f"{title} is an opening"]
        if domains:
            parts[0] += f" in the {domains} space"
        parts[0] += "."
        if must:
            parts.append(f"It requires strong proficiency in {must}.")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Candidate ↔ job semantic relevance
    # ------------------------------------------------------------------

    def relevance(self, cv_summary: str, job_summary: str) -> Dict[str, Any]:
        """Return {"relevant": bool, "summary": str} tying CV to job."""
        if self._available and cv_summary and job_summary:
            user_prompt = (
                f"CANDIDATE SUMMARY:\n{cv_summary}\n\n"
                f"JOB SUMMARY:\n{job_summary}"
            )
            try:
                raw = self._llm.complete_json(RELEVANCE_SYSTEM_PROMPT, user_prompt)
                summary = (raw.get("summary") or "").strip()
                if summary:
                    return {"relevant": bool(raw.get("relevant", False)), "summary": summary, "used_llm": True}
            except Exception:
                logger.exception("LLM relevance failed – using template fallback")
        return self._fallback_relevance(cv_summary, job_summary)

    def _fallback_relevance(self, cv_summary: str, job_summary: str) -> Dict[str, Any]:
        if not cv_summary or not job_summary:
            return {"relevant": False, "summary": "Not enough information to assess semantic relevance.", "used_llm": False}
        return {
            "relevant": True,
            "summary": (
                "Automated relevance reasoning is unavailable. Based on the parsed "
                "candidate and job summaries, review the matched skills and domain "
                "overlap above to judge fit."
            ),
            "used_llm": False,
        }
