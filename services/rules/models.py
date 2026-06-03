from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RuleConstraint:
    field: str
    operator: str  # "==", ">=", "<=", "in", "contains"
    value: object


@dataclass(frozen=True)
class RuleEvaluation:
    rule_name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class RuleResult:
    passed_all: bool
    evaluations: List[RuleEvaluation]
