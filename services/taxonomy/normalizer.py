"""Canonical skill and role taxonomy normalizer.

Maps common aliases, abbreviations, and spelling variants to their
canonical forms so that matching and scoring operate on a consistent
vocabulary regardless of how candidates or job descriptions phrase things.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class NormalizedSkills:
    skills: List[str]


# ---------------------------------------------------------------------------
# Default alias map
# ---------------------------------------------------------------------------

DEFAULT_ALIAS_MAP: Dict[str, str] = {
    # Databases
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "dynamo": "dynamodb",
    "dynamodb": "dynamodb",
    # Languages
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "c#": "csharp",
    "c++": "cpp",
    "objective-c": "objective_c",
    # Frameworks
    "next.js": "nextjs",
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "vue.js": "vue",
    "express.js": "express",
    "angular.js": "angular",
    "angularjs": "angular",
    "spring boot": "spring",
    "ruby on rails": "rails",
    # Cloud / infra
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "tf": "terraform",
    # Tools
    "ci/cd": "cicd",
    "ci cd": "cicd",
    "github actions": "github_actions",
    "gitlab ci": "gitlab_ci",
    # ML
    "sklearn": "scikit-learn",
    "sk-learn": "scikit-learn",
    "tf": "tensorflow",
    "pytorch": "pytorch",
    "huggingface": "hugging_face",
    "hugging face": "hugging_face",
    "llm": "large_language_models",
    "nlp": "natural_language_processing",
    "ml": "machine_learning",
    # Data
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "apache flink": "flink",
    "elastic search": "elasticsearch",
    "elastic": "elasticsearch",
}


class TaxonomyNormalizer:
    def __init__(self, alias_map: Dict[str, str] | None = None) -> None:
        self._alias_map = alias_map or DEFAULT_ALIAS_MAP

    def normalize_skills(self, skills: List[str]) -> NormalizedSkills:
        normalized = []
        for skill in skills:
            key = skill.strip().lower()
            canonical = self._alias_map.get(key, key)
            if canonical and canonical not in normalized:
                normalized.append(canonical)
        return NormalizedSkills(skills=normalized)
