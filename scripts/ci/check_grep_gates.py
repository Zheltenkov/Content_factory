"""Contract grep gates for architecture and migration invariants."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    rule: str
    path: Path
    line: int
    message: str


INLINE_PROMPT_RE = re.compile(
    r"\b(?:prompt|system|user|instructions)\s*=\s*f?(?P<quote>['\"]{3})(?P<body>.{400,}?)(?P=quote)",
    re.DOTALL,
)
RAW_SQL_ACCESS_RE = re.compile(
    r"(\b(?:session|connection|conn|con|engine)\.execute\s*\(|\b(?:sa|sqlalchemy)\.text\s*\()"
)
CORE_IMPORT_RE = re.compile(r"^\s*(?:from\s+app\.modules\b|import\s+app\.modules\b)", re.MULTILINE)
SKILL_ON_RE = re.compile(r"^\s*(?:-\s*)?on\s*:", re.MULTILINE)


def _iter_files(root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in root.glob(pattern) if path.is_file())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_allowed_sql_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    return (
        rel.startswith("app/") and rel.endswith("/repo.py")
        or rel.startswith("app/core/db/")
        or rel.startswith("migrations/")
    )


def check_core_imports(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_files(root, "app/core/**/*.py"):
        text = _read(path)
        for match in CORE_IMPORT_RE.finditer(text):
            violations.append(
                Violation(
                    rule="core_to_modules_import",
                    path=path,
                    line=_line_for_offset(text, match.start()),
                    message="core/* must not import app.modules.*",
                )
            )
    return violations


def check_skill_yaml_hooks(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_files(root, "app/core/methodology/**/skill.yaml"):
        text = _read(path)
        for match in SKILL_ON_RE.finditer(text):
            violations.append(
                Violation(
                    rule="skill_yaml_on",
                    path=path,
                    line=_line_for_offset(text, match.start()),
                    message="skill.yaml hook key must be 'at:', not 'on:'",
                )
            )
    return violations


def check_raw_sql_access(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_files(root, "app/**/*.py"):
        if _is_allowed_sql_path(path, root):
            continue
        text = _read(path)
        for match in RAW_SQL_ACCESS_RE.finditer(text):
            violations.append(
                Violation(
                    rule="raw_sql_access",
                    path=path,
                    line=_line_for_offset(text, match.start()),
                    message="database execute/text access belongs in repo.py or app/core/db",
                )
            )
    return violations


def check_inline_prompts(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_files(root, "app/**/*.py"):
        rel = path.relative_to(root).as_posix()
        if "/prompts/" in rel:
            continue
        text = _read(path)
        for match in INLINE_PROMPT_RE.finditer(text):
            violations.append(
                Violation(
                    rule="inline_prompt",
                    path=path,
                    line=_line_for_offset(text, match.start()),
                    message="long prompts belong in app/core/llm/prompts/<area>/<name>@v1.md",
                )
            )
    return violations


def collect_violations(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(check_core_imports(root))
    violations.extend(check_skill_yaml_hooks(root))
    violations.extend(check_raw_sql_access(root))
    violations.extend(check_inline_prompts(root))
    return sorted(violations, key=lambda item: (item.rule, item.path.as_posix(), item.line))


def run(root: Path) -> int:
    violations = collect_violations(root)
    if not violations:
        print("OK grep gates: no contract violations")
        return 0

    for violation in violations:
        rel = violation.path.relative_to(root).as_posix()
        print(f"{violation.rule} {rel}:{violation.line}: {violation.message}")
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return run(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
