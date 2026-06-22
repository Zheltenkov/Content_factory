"""Fail CI when source packages exceed their declared line budgets."""

from __future__ import annotations

import argparse
import fnmatch
import glob
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BudgetResult:
    name: str
    max_lines: int
    total_lines: int
    files: int
    budget_override: bool

    @property
    def is_over_budget(self) -> bool:
        return self.total_lines > self.max_lines

    @property
    def blocks_merge(self) -> bool:
        return self.is_over_budget and not self.budget_override


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _matches_any(path: Path, patterns: list[str], root: Path) -> bool:
    rel = _as_posix(path.relative_to(root))
    return any(fnmatch.fnmatch(rel, pattern.replace("\\", "/")) for pattern in patterns)


def _iter_budget_files(root: Path, paths: list[str], excludes: list[str]) -> list[Path]:
    files: dict[str, Path] = {}
    for pattern in paths:
        for match in glob.glob(str(root / pattern), recursive=True):
            candidate = Path(match)
            if not candidate.is_file():
                continue
            if _matches_any(candidate.resolve(), excludes, root.resolve()):
                continue
            files[_as_posix(candidate.resolve())] = candidate.resolve()
    return [files[key] for key in sorted(files)]


def _count_lines(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return 0 if text == "" else len(text.splitlines())


def load_budget_results(config_path: Path, root: Path) -> list[BudgetResult]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    packages: dict[str, dict[str, Any]] = config.get("packages") or {}
    results: list[BudgetResult] = []

    for name, package in sorted(packages.items()):
        paths = list(package.get("paths") or [])
        excludes = list(package.get("excludes") or [])
        max_lines = int(package["max_lines"])
        files = _iter_budget_files(root, paths, excludes)
        total = sum(_count_lines(path) for path in files)
        results.append(
            BudgetResult(
                name=name,
                max_lines=max_lines,
                total_lines=total,
                files=len(files),
                budget_override=bool(package.get("budget_override")),
            )
        )
    return results


def run(config_path: Path, root: Path) -> int:
    results = load_budget_results(config_path=config_path, root=root)
    failures = [result for result in results if result.blocks_merge]

    for result in results:
        if result.blocks_merge:
            status = "FAIL"
        elif result.is_over_budget:
            status = "OVERRIDE"
        else:
            status = "OK"
        override = " override" if result.budget_override else ""
        print(
            f"{status} {result.name}: {result.total_lines}/{result.max_lines} lines "
            f"across {result.files} files{override}"
        )

    if failures:
        print("\nLine budget exceeded:")
        for failure in failures:
            print(f"- {failure.name}: {failure.total_lines} > {failure.max_lines}")
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="line_budget.yaml", help="Path to line_budget.yaml")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    return run(config_path=config_path.resolve(), root=root)


if __name__ == "__main__":
    raise SystemExit(main())
