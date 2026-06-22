"""Detect large copy-pasted Python and JavaScript function bodies in app/."""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionFingerprint:
    path: Path
    name: str
    line: int
    lines: int
    language: str
    digest: str


JS_FUNCTION_PATTERNS = (
    re.compile(r"\bfunction\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
    re.compile(r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\([^)]*\)\s*\{"),
    re.compile(
        r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{"
    ),
)


def _iter_source_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in (root / "app").glob(f"**/*{suffix}") if path.is_file())


def _function_lines(node: ast.AST) -> int:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    return max(0, end - start + 1)


def _function_name(node: ast.AST) -> str:
    return getattr(node, "name", "<anonymous>")


def _python_fingerprint(node: ast.AST) -> str:
    body = getattr(node, "body", [])
    normalized = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
    return hashlib.sha256(f"py:{normalized}".encode("utf-8")).hexdigest()


def _collect_python_fingerprints(root: Path, min_lines: int) -> list[FunctionFingerprint]:
    fingerprints: list[FunctionFingerprint] = []
    for path in _iter_source_files(root, ".py"):
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
                    language="py",
                    digest=_python_fingerprint(node),
                )
            )
    return fingerprints


def _js_function_name(line: str) -> str | None:
    for pattern in JS_FUNCTION_PATTERNS:
        match = pattern.search(line)
        if match is not None:
            return str(match.group("name"))
    return None


def _js_function_end(lines: list[str], start: int) -> int | None:
    balance = 0
    seen_open_brace = False
    for index in range(start, len(lines)):
        line = lines[index]
        if not seen_open_brace:
            brace_pos = line.find("{")
            if brace_pos == -1:
                continue
            seen_open_brace = True
            line = line[brace_pos:]
        balance += line.count("{") - line.count("}")
        if seen_open_brace and balance <= 0:
            return index
    return None


def _js_fingerprint(lines: list[str]) -> str:
    normalized = "\n".join(line.strip() for line in lines if line.strip())
    return hashlib.sha256(f"js:{normalized}".encode("utf-8")).hexdigest()


def _collect_javascript_fingerprints(root: Path, min_lines: int) -> list[FunctionFingerprint]:
    fingerprints: list[FunctionFingerprint] = []
    for path in _iter_source_files(root, ".js"):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            name = _js_function_name(line)
            if name is None:
                continue
            end = _js_function_end(lines, index)
            if end is None:
                continue
            function_lines = lines[index : end + 1]
            line_count = len(function_lines)
            if line_count < min_lines:
                continue
            fingerprints.append(
                FunctionFingerprint(
                    path=path,
                    name=name,
                    line=index + 1,
                    lines=line_count,
                    language="js",
                    digest=_js_fingerprint(function_lines),
                )
            )
    return fingerprints


def collect_fingerprints(root: Path, min_lines: int) -> list[FunctionFingerprint]:
    return [
        *_collect_python_fingerprints(root, min_lines=min_lines),
        *_collect_javascript_fingerprints(root, min_lines=min_lines),
    ]


def find_duplicates(root: Path, min_lines: int) -> dict[str, list[FunctionFingerprint]]:
    grouped: dict[str, list[FunctionFingerprint]] = {}
    for fingerprint in collect_fingerprints(root, min_lines=min_lines):
        grouped.setdefault(fingerprint.digest, []).append(fingerprint)
    return {digest: items for digest, items in grouped.items() if len(items) > 1}


def run(root: Path, min_lines: int) -> int:
    duplicates = find_duplicates(root, min_lines=min_lines)
    if not duplicates:
        print(f"OK duplicates: no duplicated Python/JavaScript functions >= {min_lines} lines")
        return 0

    for items in duplicates.values():
        print("duplicate_function:")
        for item in items:
            rel = item.path.relative_to(root).as_posix()
            print(f"- {rel}:{item.line} {item.name} [{item.language}] ({item.lines} lines)")
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
