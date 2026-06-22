from __future__ import annotations

import subprocess
import sys
import shutil
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "scripts" / "ci"
TMP_ROOT = ROOT / "pytest-cache-files-ci"


def make_tmp_repo() -> Path:
    path = TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path


def cleanup_tmp_repo(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def run_gate(script: str, tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CI / script), "--root", str(tmp_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_line_budget_fails_when_package_exceeds_limit() -> None:
    tmp_path = make_tmp_repo()
    try:
        source = tmp_path / "pkg"
        source.mkdir()
        (source / "module.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        (tmp_path / "line_budget.yaml").write_text(
            """
packages:
  demo:
    paths:
      - pkg/*.py
    max_lines: 2
""".strip(),
            encoding="utf-8",
        )

        result = run_gate("check_line_budget.py", tmp_path)

        assert result.returncode == 1
        assert "demo: 3/2" in result.stdout
    finally:
        cleanup_tmp_repo(tmp_path)


def test_grep_gates_catch_architecture_contract_violations() -> None:
    tmp_path = make_tmp_repo()
    try:
        (tmp_path / "app" / "core" / "methodology" / "profiles" / "_base" / "skills" / "bad").mkdir(
            parents=True
        )
        (tmp_path / "app" / "modules" / "feature").mkdir(parents=True)
        (tmp_path / "app" / "core" / "bad_import.py").write_text(
            "from app.modules.feature import service\n",
            encoding="utf-8",
        )
        (
            tmp_path
            / "app"
            / "core"
            / "methodology"
            / "profiles"
            / "_base"
            / "skills"
            / "bad"
            / "skill.yaml"
        ).write_text(
            "id: bad\nhooks:\n  - on: checker.evaluation\n",
            encoding="utf-8",
        )
        (tmp_path / "app" / "modules" / "feature" / "service.py").write_text(
            "def bad(conn):\n    conn.execute('SELECT 1')\n",
            encoding="utf-8",
        )
        (tmp_path / "app" / "modules" / "feature" / "prompt.py").write_text(
            'prompt = """' + ("Следуй правилам. " * 40) + '"""\n',
            encoding="utf-8",
        )

        result = run_gate("check_grep_gates.py", tmp_path)

        assert result.returncode == 1
        assert "core_to_modules_import" in result.stdout
        assert "skill_yaml_on" in result.stdout
        assert "raw_sql_access" in result.stdout
        assert "inline_prompt" in result.stdout
    finally:
        cleanup_tmp_repo(tmp_path)


def test_duplicate_detector_catches_large_copied_functions() -> None:
    tmp_path = make_tmp_repo()
    try:
        (tmp_path / "app" / "a").mkdir(parents=True)
        (tmp_path / "app" / "b").mkdir(parents=True)
        body = "\n".join(f"    total += value + {idx}" for idx in range(12))
        function = f"def copied(value):\n    total = 0\n{body}\n    return total\n"
        (tmp_path / "app" / "a" / "one.py").write_text(function, encoding="utf-8")
        (tmp_path / "app" / "b" / "two.py").write_text(function, encoding="utf-8")

        result = run_gate("check_duplicates.py", tmp_path, "--min-lines", "8")

        assert result.returncode == 1
        assert "duplicate_function" in result.stdout
        assert "one.py" in result.stdout
        assert "two.py" in result.stdout
    finally:
        cleanup_tmp_repo(tmp_path)
