"""Sandboxed execution of generated code.

Runs untrusted (AI-generated) code in a separate subprocess:

  * fresh interpreter with ``-I`` (isolated: ignores env vars, user site-packages,
    and does not put the script directory on sys.path)
  * hard wall-clock timeout (kills the process group)
  * cwd set to a throwaway temp directory
  * a small preamble that strips a few obviously dangerous builtins
    (this is defence-in-depth, trivially bypassable)

SECURITY NOTE — this is BEST-EFFORT isolation for benchmark hygiene, not a
security boundary. Generated code still runs with the invoking user's OS
permissions. Do not point this harness at genuinely hostile code outside a
container/VM. (The mock corpus is shipped with the repo and reviewed.)
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Best-effort namespace restriction, prepended to every sandboxed script.
# Solutions that legitimately need os/subprocess (e.g. list_files) still work:
# this only removes interactive/exit escape hatches from builtins.
_PREAMBLE = """\
import builtins as _b
for _name in ("input", "breakpoint", "exit", "quit", "help"):
    if hasattr(_b, _name):
        delattr(_b, _name)
del _b, _name
"""


@dataclass
class SandboxResult:
    ok: bool  # exit code 0 and no timeout
    timed_out: bool
    exit_code: int | None
    stdout: str
    stderr: str

    @property
    def failure_summary(self) -> str:
        if self.timed_out:
            return "timeout"
        if self.ok:
            return ""
        tail = self.stderr.strip().splitlines()
        return tail[-1] if tail else f"exit code {self.exit_code}"


def run_snippet(
    code: str,
    timeout_s: float = 5.0,
    python: str | None = None,
) -> SandboxResult:
    """Execute a Python source string in an isolated subprocess."""
    python = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="codegeneval-sbx-") as td:
        script = Path(td) / "snippet.py"
        script.write_text(_PREAMBLE + "\n" + code)
        try:
            proc = subprocess.run(
                [python, "-I", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=td,
                start_new_session=True,  # own process group -> clean kill on timeout
            )
        except subprocess.TimeoutExpired as exc:
            _reap(exc)
            return SandboxResult(
                ok=False,
                timed_out=True,
                exit_code=None,
                stdout=_txt(exc.stdout),
                stderr=_txt(exc.stderr),
            )
        return SandboxResult(
            ok=proc.returncode == 0,
            timed_out=False,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


def run_solution_with_checks(
    solution_code: str,
    check_code: str,
    timeout_s: float = 5.0,
) -> SandboxResult:
    """Run solution + check snippet(s) as one sandboxed script.

    The check code runs after the solution's top-level definitions, so it can
    call the solution's functions directly (assert-style reference tests).
    """
    script = solution_code + "\n\n# --- harness checks ---\n" + check_code
    return run_snippet(script, timeout_s=timeout_s)


def _txt(b) -> str:
    if b is None:
        return ""
    return b if isinstance(b, str) else b.decode(errors="replace")


def _reap(exc: subprocess.TimeoutExpired) -> None:
    """Best-effort: make sure a timed-out process group is gone."""
    # subprocess.run already killed the direct child; grandchildren in the
    # session are covered by start_new_session + the kill below when possible.
    pid = getattr(exc, "pid", None) or getattr(getattr(exc, "process", None), "pid", None)
    if pid:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
