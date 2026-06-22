"""Detect large copy-pasted Python function bodies in app/."""

from __future__ import annotations

import argparse
import ast
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionFingerprint:
    path: Path
    name: str
    line: int
    lines: int
    digest: str


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in (root / "app").glob("**/*.py") if path.is_file())


def _function_lines(node: ast.AST) -> int:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    return max(0, end - start + 1)


def _function_name(node: ast.AST) -> str:
    return getattr(node, "name", "<anonymous>")


def _fingerprint(node: ast.AST) -> str:
    body = getattr(node, "body", [])
    normalized = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collect_fingerprints(root: Path, min_lines: int) -> list[FunctionFingerprint]:
    fingerprints: list[FunctionFingerprint] = []
    for path in _iter_python_files(root):
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lines = _function_lines(node)
            if lines < min_lines:
                continue
            fingerprints.append(
                FunctionFingerprint(
                    path=path,
                    name=_function_name(node),
                    line=int(getattr(node, "lineno", 1)),
                    lines=lines,
                    digest=_fingerprint(node),
                )
            )
    return fingerprints


def find_duplicates(root: Path, min_lines: int) -> dict[str, list[FunctionFingerprint]]:
    grouped: dict[str, list[FunctionFingerprint]] = {}
    for fingerprint in collect_fingerprints(root, min_lines=min_lines):
        grouped.setdefault(fingerprint.digest, []).append(fingerprint)
    return {digest: items for digest, items in grouped.items() if len(items) > 1}


def run(root: Path, min_lines: int) -> int:
    duplicates = find_duplicates(root, min_lines=min_lines)
    if not duplicates:
        print(f"OK duplicates: no duplicated Python functions >= {min_lines} lines")
        return 0

    for items in duplicates.values():
        print("duplicate_function:")
        for item in items:
            rel = item.path.relative_to(root).as_posix()
            print(f"- {rel}:{item.line} {item.name} ({item.lines} lines)")
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--min-lines", type=int, default=35, help="Minimum function size to compare")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return run(root=Path(args.root).resolve(), min_lines=args.min_lines)


if __name__ == "__main__":
    raise SystemExit(main())
