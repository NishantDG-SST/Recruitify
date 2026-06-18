"""LLM-as-judge scoring of a candidate against a job's parsed requirements.

Replaces the hardcoded keyword/synonym matching: the LLM reads the structured
job requirements and candidate profile (both already in the DB) and returns
category scores + matched/missing skills, judged *semantically*. Falls back to a
minimal token matcher when the LLM is unavailable.

The LLM's matched/missing lists are treated only as a signal — callers reconcile
them back onto the canonical job requirement list via ``_requirement_satisfied``,
which is robust to both wording drift (false fail) and omission (false pass).
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


JUDGE_SYSTEM_PROMPT = """\
You are an expert technical recruiter scoring how well a candidate fits a job.
You are given the JOB REQUIREMENTS and the CANDIDATE PROFILE (both already parsed).

Judge fit by MEANING, not literal keyword equality — recognise synonyms,
abbreviations and adjacent/parent domains. For example: "postgresql" == "postgres";
"k8s" == "kubernetes"; CRO / clinical-trials work IS "life sciences" /
"pharmaceutical" experience. But do NOT conflate genuinely different skills
(e.g. "java" is NOT "javascript").

Return ONLY a JSON object (no markdown fences):
{
  "hard_skills": <integer 0-100>,        // how well the candidate's technical skills cover the job's must-have + nice-to-have skills
  "domain_knowledge": <integer 0-100>,   // alignment of the candidate's industry/domain background with the job's domain
  "soft_skills": <integer 0-100>,        // alignment of soft skills
  "matched_skills": [ ... ],             // job requirements the candidate DOES satisfy — copy each requirement's wording VERBATIM from the provided lists
  "missing_skills": [ ... ],             // job requirements the candidate does NOT satisfy — VERBATIM
  "reasoning": "1-2 sentence justification"
}

Rules:
- Consider every entry in must_have_skills and nice_to_have_skills. Each such
  requirement must appear in EXACTLY ONE of matched_skills or missing_skills,
  copied verbatim.
- Judge only from the provided candidate skills, domains, soft skills, roles and experience.
- Scores are integers 0-100."""


def _tokens(text: str) -> set:
    """Split a skill/phrase into whole-word tokens (keeps + and # for c++/c#)."""
    return {t for t in re.split(r"[^a-z0-9+#]+", str(text).lower()) if t}


def _tolerant_hit(req: str, candidates: List[str]) -> bool:
    """True if `req` whole-word-matches any entry in `candidates` (subset either way).

    Handles wording drift like "react" vs "react.js" (token subset) and casing,
    without conflating distinct skills like "java" vs "javascript" (disjoint tokens).
    """
    rt = _tokens(req)
    if not rt:
        return False
    for c in candidates or []:
        ct = _tokens(c)
        if ct and (rt <= ct or ct <= rt):
            return True
    return False


def _requirement_satisfied(
    req: str,
    judge_matched: List[str],
    judge_missing: List[str],
    cand_skills: List[str],
    cand_domains: List[str],
) -> bool:
    """Decide a single canonical requirement with a 3-way rule.

    Robust to LLM wording drift (false fail) AND omission/truncation (false pass):
    falls back to concrete evidence in the candidate's own skills/domains rather
    than blindly defaulting either way.
    """
    in_matched = _tolerant_hit(req, judge_matched)
    in_missing = _tolerant_hit(req, judge_missing)
    if in_matched and not in_missing:
        return True
    if in_missing and not in_matched:
        return False
    # Omitted by the LLM, or listed in both → require real evidence in the candidate.
    return _tolerant_hit(req, list(cand_skills or []) + list(cand_domains or []))


def reconcile_requirements(
    job_parsed: Dict[str, Any],
    fit: Dict[str, Any],
    cand_skills: List[str],
    cand_domains: List[str],
) -> tuple:
    """Reconcile the LLM's matched/missing back onto the canonical job requirements.

    Returns (matched, missing) using the job's own wording so display and the
    must-have gate are always consistent.
    """
    canonical = (job_parsed.get("must_have_skills") or []) + (job_parsed.get("nice_to_have_skills") or [])
    matched_judge = fit.get("matched_skills") or []
    missing_judge = fit.get("missing_skills") or []
    matched = [r for r in canonical if _requirement_satisfied(r, matched_judge, missing_judge, cand_skills, cand_domains)]
    matched_set = set(matched)
    missing = [r for r in canonical if r not in matched_set]
    return matched, missing


def _build_user_prompt(job_parsed: Dict[str, Any], profile: Dict[str, Any]) -> str:
    def j(v: Any) -> str:
        return ", ".join(str(x) for x in (v or [])) or "none"
    return (
        "JOB REQUIREMENTS\n"
        f"- title: {job_parsed.get('title', '')}\n"
        f"- must_have_skills: {j(job_parsed.get('must_have_skills'))}\n"
        f"- nice_to_have_skills: {j(job_parsed.get('nice_to_have_skills'))}\n"
        f"- domains: {j(job_parsed.get('domains'))}\n"
        f"- soft_skills: {j(job_parsed.get('soft_skills'))}\n\n"
        "CANDIDATE PROFILE\n"
        f"- skills: {j(profile.get('skills'))}\n"
        f"- domains: {j(profile.get('domains'))}\n"
        f"- soft_skills: {j(profile.get('soft_skills'))}\n"
        f"- roles: {j(profile.get('roles'))}\n"
        f"- years_experience: {profile.get('years_experience', '?')}\n"
    )


def _clamp_score(v: Any) -> float:
    try:
        return max(0.0, min(100.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _as_str_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if isinstance(x, (str, int, float)) and str(x).strip()]


def score_fit(job_parsed: Dict[str, Any], profile: Dict[str, Any], llm: Optional[Any] = None) -> Dict[str, Any]:
    """Score a candidate against a job. Uses the LLM judge, falling back to a token matcher."""
    if llm is not None and getattr(llm, "is_available", False):
        try:
            raw = llm.complete_json(JUDGE_SYSTEM_PROMPT, _build_user_prompt(job_parsed, profile), max_tokens=1024)
            return {
                "hard_skills": _clamp_score(raw.get("hard_skills")),
                "soft_skills": _clamp_score(raw.get("soft_skills")),
                "domain_knowledge": _clamp_score(raw.get("domain_knowledge")),
                "matched_skills": _as_str_list(raw.get("matched_skills")),
                "missing_skills": _as_str_list(raw.get("missing_skills")),
                "reasoning": str(raw.get("reasoning") or ""),
                "method": "llm",
            }
        except Exception:
            logger.exception("LLM fit judge failed — using token fallback")
    return _fallback_score(job_parsed, profile)


def _fallback_score(job_parsed: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic minimal matcher when the LLM is unavailable (no synonym maps)."""
    must = job_parsed.get("must_have_skills") or []
    nice = job_parsed.get("nice_to_have_skills") or []
    canonical = must + nice
    cand_skills = profile.get("skills") or []
    cand_domains = profile.get("domains") or []
    evidence = list(cand_skills) + list(cand_domains)

    matched = [r for r in canonical if _tolerant_hit(r, evidence)]
    missing = [r for r in canonical if r not in set(matched)]
    hard = (len(matched) / len(canonical) * 100.0) if canonical else 100.0

    job_domains = job_parsed.get("domains") or []
    dom_hits = sum(1 for d in job_domains if _tolerant_hit(d, cand_domains))
    domain = (dom_hits / len(job_domains) * 100.0) if job_domains else 0.0

    job_soft = job_parsed.get("soft_skills") or []
    cand_soft = profile.get("soft_skills") or []
    soft_hits = sum(1 for s in job_soft if _tolerant_hit(s, cand_soft))
    soft = (soft_hits / len(job_soft) * 100.0) if job_soft else 0.0

    return {
        "hard_skills": round(hard, 1),
        "soft_skills": round(soft, 1),
        "domain_knowledge": round(domain, 1),
        "matched_skills": matched,
        "missing_skills": missing,
        "reasoning": "Scored without LLM (token fallback).",
        "method": "fallback",
    }
