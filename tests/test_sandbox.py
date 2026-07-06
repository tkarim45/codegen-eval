"""Sandbox: exit codes, assertion failures, timeouts, check composition."""
import time

from codegeneval.sandbox import run_snippet, run_solution_with_checks


def test_ok_snippet():
    result = run_snippet("x = 1 + 1\nassert x == 2\n")
    assert result.ok
    assert not result.timed_out
    assert result.exit_code == 0


def test_failing_assert_is_not_ok():
    result = run_snippet("assert 1 == 2, 'nope'\n")
    assert not result.ok
    assert not result.timed_out
    assert "AssertionError" in result.stderr
    assert "AssertionError" in result.failure_summary


def test_exception_is_not_ok():
    result = run_snippet("raise ValueError('boom')\n")
    assert not result.ok
    assert "ValueError" in result.stderr


def test_timeout_is_flagged_and_bounded():
    start = time.monotonic()
    result = run_snippet("while True:\n    pass\n", timeout_s=1.0)
    elapsed = time.monotonic() - start
    assert result.timed_out
    assert not result.ok
    assert result.failure_summary == "timeout"
    assert elapsed < 10  # the wall-clock kill actually fires


def test_solution_plus_checks_composition():
    solution = "def double(x):\n    return 2 * x\n"
    good = run_solution_with_checks(solution, "assert double(3) == 6")
    bad = run_solution_with_checks(solution, "assert double(3) == 7")
    assert good.ok
    assert not bad.ok


def test_stdout_captured():
    result = run_snippet("print('hello-sandbox')\n")
    assert result.ok
    assert "hello-sandbox" in result.stdout


def test_restricted_builtins_removed():
    # Best-effort restriction: interactive escape hatches are stripped.
    result = run_snippet("input('x')\n", timeout_s=3.0)
    assert not result.ok
