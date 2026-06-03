"""Bias and diversity analysis for ranking outputs.

Analyses score distributions, detects homogeneous shortlists, and flags
candidates with non-traditional backgrounds who score well but might be
overlooked.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CandidateProfile:
    """Minimal profile slice needed for bias analysis."""

    candidate_snapshot_id: str
    final_score: float
    education_level: str = "unknown"
    years_experience: int = 0
    career_trajectory: str = "unknown"
    domains: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class BiasFlag:
    """A single bias or diversity concern."""

    flag_type: str
    severity: str          # "info" | "warning" | "critical"
    message: str
    affected_candidates: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class BiasAnalysisResult:
    """Full bias analysis output for a ranking run."""

    metrics: Dict[str, float]
    warnings: List[str]
    flags: List[BiasFlag] = field(default_factory=list)
    hidden_gems: List[str] = field(default_factory=list)


class BiasAnalyzer:
    """Detect statistical bias and homogeneity in ranking outputs."""

    def __init__(
        self,
        homogeneity_threshold: float = 0.7,
        score_gap_threshold: float = 15.0,
        hidden_gem_min_score: float = 60.0,
    ) -> None:
        self._homogeneity_threshold = homogeneity_threshold
        self._score_gap_threshold = score_gap_threshold
        self._hidden_gem_min_score = hidden_gem_min_score

    def analyze(
        self,
        scores: List[float],
        profiles: Optional[List[CandidateProfile]] = None,
    ) -> BiasAnalysisResult:
        """Run bias analysis on a set of candidate scores and profiles."""
        if not scores:
            return BiasAnalysisResult(metrics={}, warnings=["no_scores"])

        metrics = self._compute_distribution_metrics(scores)
        flags: List[BiasFlag] = []
        warnings: List[str] = []
        hidden_gems: List[str] = []

        # --- Score distribution checks ---
        if metrics.get("std_dev", 0) < 5.0 and len(scores) > 3:
            flags.append(BiasFlag(
                flag_type="low_variance",
                severity="warning",
                message=(
                    f"Score standard deviation is very low ({metrics['std_dev']:.1f}). "
                    "This may indicate the scoring model is not differentiating candidates."
                ),
            ))
            warnings.append("low_score_variance")

        if metrics.get("score_gap_top", 0) > self._score_gap_threshold:
            flags.append(BiasFlag(
                flag_type="score_cliff",
                severity="info",
                message=(
                    f"Large gap ({metrics['score_gap_top']:.1f}) between top candidate "
                    "and second-best. Review whether the top score is inflated."
                ),
            ))
            warnings.append("score_cliff_detected")

        # --- Profile-based diversity checks ---
        if profiles and len(profiles) >= 3:
            edu_flags, edu_gems = self._analyze_education_diversity(profiles)
            flags.extend(edu_flags)
            hidden_gems.extend(edu_gems)

            traj_flags = self._analyze_trajectory_diversity(profiles)
            flags.extend(traj_flags)

            domain_flags = self._analyze_domain_concentration(profiles)
            flags.extend(domain_flags)

        if not warnings and not flags:
            warnings.append("no_issues_detected")

        return BiasAnalysisResult(
            metrics=metrics,
            warnings=warnings,
            flags=flags,
            hidden_gems=hidden_gems,
        )

    # ------------------------------------------------------------------
    # Distribution metrics
    # ------------------------------------------------------------------

    def _compute_distribution_metrics(self, scores: List[float]) -> Dict[str, float]:
        n = len(scores)
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / n
        std_dev = math.sqrt(variance)
        sorted_scores = sorted(scores, reverse=True)

        metrics: Dict[str, float] = {
            "count": float(n),
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "median": round(sorted_scores[n // 2], 2),
        }

        if n >= 2:
            metrics["score_gap_top"] = round(sorted_scores[0] - sorted_scores[1], 2)

        if n >= 4:
            q1 = sorted_scores[3 * n // 4]
            q3 = sorted_scores[n // 4]
            metrics["iqr"] = round(q3 - q1, 2)
            metrics["skewness"] = round(
                (3.0 * (mean - sorted_scores[n // 2])) / std_dev if std_dev > 0 else 0, 2
            )

        return metrics

    # ------------------------------------------------------------------
    # Education diversity
    # ------------------------------------------------------------------

    def _analyze_education_diversity(
        self, profiles: List[CandidateProfile]
    ) -> tuple[List[BiasFlag], List[str]]:
        shortlisted = [p for p in profiles if p.final_score >= self._hidden_gem_min_score]
        if len(shortlisted) < 2:
            return [], []

        edu_counts: Dict[str, int] = {}
        for p in shortlisted:
            edu_counts[p.education_level] = edu_counts.get(p.education_level, 0) + 1

        flags: List[BiasFlag] = []
        hidden_gems: List[str] = []

        dominant_edu = max(edu_counts, key=lambda k: edu_counts[k])
        ratio = edu_counts[dominant_edu] / len(shortlisted)
        if ratio >= self._homogeneity_threshold and len(edu_counts) <= 2:
            flags.append(BiasFlag(
                flag_type="education_homogeneity",
                severity="warning",
                message=(
                    f"{ratio:.0%} of shortlisted candidates share the same education "
                    f"level ({dominant_edu}). Consider reviewing candidates with "
                    "non-traditional education backgrounds."
                ),
            ))

        # Identify hidden gems: non-traditional education but strong score
        traditional = {"bachelors", "masters", "phd"}
        for p in profiles:
            if (
                p.education_level not in traditional
                and p.final_score >= self._hidden_gem_min_score
            ):
                hidden_gems.append(p.candidate_snapshot_id)

        return flags, hidden_gems

    # ------------------------------------------------------------------
    # Career trajectory diversity
    # ------------------------------------------------------------------

    def _analyze_trajectory_diversity(self, profiles: List[CandidateProfile]) -> List[BiasFlag]:
        shortlisted = [p for p in profiles if p.final_score >= self._hidden_gem_min_score]
        if len(shortlisted) < 3:
            return []

        traj_counts: Dict[str, int] = {}
        for p in shortlisted:
            traj_counts[p.career_trajectory] = traj_counts.get(p.career_trajectory, 0) + 1

        dominant = max(traj_counts, key=lambda k: traj_counts[k])
        ratio = traj_counts[dominant] / len(shortlisted)

        if ratio >= self._homogeneity_threshold:
            return [BiasFlag(
                flag_type="trajectory_homogeneity",
                severity="info",
                message=(
                    f"{ratio:.0%} of shortlisted candidates have a '{dominant}' "
                    "career trajectory. The shortlist may lack diverse career paths."
                ),
            )]
        return []

    # ------------------------------------------------------------------
    # Domain concentration
    # ------------------------------------------------------------------

    def _analyze_domain_concentration(self, profiles: List[CandidateProfile]) -> List[BiasFlag]:
        shortlisted = [p for p in profiles if p.final_score >= self._hidden_gem_min_score]
        if len(shortlisted) < 3:
            return []

        domain_counts: Dict[str, int] = {}
        for p in shortlisted:
            for d in p.domains:
                domain_counts[d] = domain_counts.get(d, 0) + 1

        if not domain_counts:
            return []

        dominant = max(domain_counts, key=lambda k: domain_counts[k])
        ratio = domain_counts[dominant] / len(shortlisted)

        if ratio >= self._homogeneity_threshold:
            return [BiasFlag(
                flag_type="domain_concentration",
                severity="info",
                message=(
                    f"{ratio:.0%} of shortlisted candidates come from the '{dominant}' "
                    "domain. Cross-industry candidates may bring valuable perspectives."
                ),
            )]
        return []
