"""Checker module: structural and didactic evaluation axes."""

from app.modules.checker.didactic import DidacticQualityReport, evaluate_didactic
from app.modules.checker.service import CheckerDeterministicResult, ContentSufficiencyResult, evaluate_content_sufficiency, evaluate_deterministic
from app.modules.checker.structural import StructuralAxisResult, evaluate_document, evaluate_readme, run

__all__ = [
    "CheckerDeterministicResult",
    "ContentSufficiencyResult",
    "DidacticQualityReport",
    "StructuralAxisResult",
    "evaluate_content_sufficiency",
    "evaluate_deterministic",
    "evaluate_didactic",
    "evaluate_document",
    "evaluate_readme",
    "run",
]
