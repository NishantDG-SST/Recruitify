from typing import Any, Dict, List

from services.rules.models import RuleConstraint, RuleEvaluation, RuleResult


class RulesEngine:
    def evaluate(self, candidate_features: Dict[str, Any], rules: List[RuleConstraint]) -> RuleResult:
        evaluations: List[RuleEvaluation] = []
        passed_all = True

        for rule in rules:
            actual_val = candidate_features.get(rule.field)
            passed, reason = self._evaluate_rule(rule, actual_val)
            
            if not passed:
                passed_all = False
                
            evaluations.append(RuleEvaluation(
                rule_name=f"{rule.field} {rule.operator} {rule.value}",
                passed=passed,
                reason=reason
            ))

        return RuleResult(passed_all=passed_all, evaluations=evaluations)

    def _evaluate_rule(self, rule: RuleConstraint, actual_val: Any) -> tuple[bool, str]:
        if actual_val is None:
            return False, f"Missing field '{rule.field}'"

        try:
            if rule.operator == "==":
                passed = actual_val == rule.value
            elif rule.operator == ">=":
                passed = float(actual_val) >= float(rule.value)
            elif rule.operator == "<=":
                passed = float(actual_val) <= float(rule.value)
            elif rule.operator == "in":
                passed = actual_val in rule.value
            elif rule.operator == "contains":
                if isinstance(actual_val, list):
                    passed = rule.value in actual_val
                elif isinstance(actual_val, str):
                    passed = str(rule.value).lower() in actual_val.lower()
                else:
                    passed = False
            else:
                return False, f"Unknown operator '{rule.operator}'"
        except (ValueError, TypeError):
            return False, f"Type mismatch comparing {actual_val} and {rule.value}"

        if passed:
            return True, "Passed"
        return False, f"Value '{actual_val}' failed '{rule.operator} {rule.value}' constraint"
