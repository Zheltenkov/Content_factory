"""Generator stage implementations."""

from app.modules.generator.stages.generators import GeneratorAssetsResult, generate_assets, run as run_generators
from app.modules.generator.stages.head import HeadResult, generate_head, run as run_head
from app.modules.generator.stages.practice import PracticeResult, generate_practice, run as run_practice
from app.modules.generator.stages.practice_review import PracticeReviewResult, review_practice, run as run_practice_review
from app.modules.generator.stages.theory import TheoryResult, generate_theory, run as run_theory

run = run_head

__all__ = [
    "GeneratorAssetsResult",
    "HeadResult",
    "PracticeResult",
    "PracticeReviewResult",
    "TheoryResult",
    "generate_assets",
    "generate_head",
    "generate_practice",
    "generate_theory",
    "review_practice",
    "run",
    "run_generators",
    "run_head",
    "run_practice",
    "run_practice_review",
    "run_theory",
]
