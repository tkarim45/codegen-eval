"""Unit-test layer — the task's reference tests, run in the sandbox.

Three sub-sections, each its own sandboxed run so the report can say WHICH
kind of test failed:

    basic   the happy-path reference tests   (catches wrong-logic)
    edge    the boundary/edge-case tests     (catches missed-edge-case,
                                              silent-type-error crashes)
    perf    a timed test on large input      (catches performance-trap via
                                              the sandbox timeout)
"""
from __future__ import annotations

from .. import sandbox
from ..tasks import Task
from . import FAIL, PASS, LayerResult


def run(code: str, task: Task, config) -> LayerResult:
    failures: list[str] = []

    basic = sandbox.run_solution_with_checks(
        code, "\n\n".join(task.tests), timeout_s=config.timeout_s
    )
    if not basic.ok:
        failures.append(f"basic: {basic.failure_summary}")

    if task.edge_tests:
        edge = sandbox.run_solution_with_checks(
            code, "\n\n".join(task.edge_tests), timeout_s=config.timeout_s
        )
        if not edge.ok:
            failures.append(f"edge: {edge.failure_summary}")

    if task.perf_test:
        perf = sandbox.run_solution_with_checks(
            code, task.perf_test["code"], timeout_s=float(task.perf_test["timeout_s"])
        )
        if not perf.ok:
            label = "timeout" if perf.timed_out else perf.failure_summary
            failures.append(f"perf: {label}")

    if failures:
        return LayerResult("unit", FAIL, "; ".join(failures), {"sections": failures})
    return LayerResult("unit", PASS, "basic+edge+perf green")
