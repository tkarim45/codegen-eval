"""Static/security lint layer.

Three detectors, results unioned:

  * built-in insecure-pattern scanner — ALWAYS on, zero dependencies, so the
    mock pipeline catches eval/exec/shell-injection offline
  * bandit  (dev extra) — full security lint, used when installed
  * ruff    (dev extra) — `--select S` (flake8-bandit rules), used when installed

Both external tools degrade gracefully to "not installed" notes.
Verdict: FAIL if any detector reports a security finding.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..tasks import Task
from . import FAIL, PASS, LayerResult

# Built-in detectors: (finding id, compiled pattern). Deliberately high-precision
# patterns aimed at the taxonomy's insecure-pattern class.
_BUILTIN = [
    ("use-of-eval", re.compile(r"(?<![\w.])eval\s*\(")),
    ("use-of-exec", re.compile(r"(?<![\w.])exec\s*\(")),
    ("shell-true", re.compile(r"shell\s*=\s*True")),
    ("os-system", re.compile(r"(?<![\w.])os\.system\s*\(")),
    ("pickle-loads", re.compile(r"pickle\.loads?\s*\(")),
    ("yaml-unsafe-load", re.compile(r"yaml\.load\s*\((?![^)]*SafeLoader)")),
]


def _builtin_scan(code: str) -> list[str]:
    return [name for name, pat in _BUILTIN if pat.search(code)]


def _run_bandit(path: Path) -> list[str] | None:
    exe = shutil.which("bandit")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "-f", "json", "-q", str(path)], capture_output=True, text=True, timeout=30
        )
        report = json.loads(proc.stdout or "{}")
        return [f"bandit:{r['test_id']}" for r in report.get("results", [])]
    except Exception:
        return None


def _run_ruff(path: Path) -> list[str] | None:
    exe = shutil.which("ruff")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "check", "--select", "S", "--output-format", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        findings = json.loads(proc.stdout or "[]")
        return [f"ruff:{f['code']}" for f in findings if f.get("code")]
    except Exception:
        return None


def run(code: str, task: Task, config) -> LayerResult:
    findings = _builtin_scan(code)
    notes = ["builtin scanner: on"]

    with tempfile.TemporaryDirectory(prefix="codegeneval-lint-") as td:
        path = Path(td) / "solution.py"
        path.write_text(code)
        for name, runner in (("bandit", _run_bandit), ("ruff", _run_ruff)):
            result = runner(path)
            if result is None:
                notes.append(f"{name}: not installed (skipped)")
            else:
                notes.append(f"{name}: {len(result)} finding(s)")
                findings.extend(result)

    findings = sorted(set(findings))
    extra = {"findings": findings, "detectors": notes}
    if findings:
        return LayerResult("lint", FAIL, "security findings: " + ", ".join(findings), extra)
    return LayerResult("lint", PASS, "; ".join(notes), extra)
