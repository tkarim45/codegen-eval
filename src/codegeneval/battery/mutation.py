"""Mutation-testing layer — how trustworthy is a green test run?

A tiny built-in AST mutator (no mutmut dependency; mutmut stays a dev extra
for comparison runs) generates first-order mutants of the GENERATED solution:

    ==  <->  !=      <  ->  <=      >  ->  >=
    +   <->  -       and <-> or     integer constant n -> n + 1

Each mutant is re-run against the task's reference tests in the sandbox. A
mutant that still passes ("survives") means the tests never pinned that part
of the behavior — so a green unit run is weaker evidence than it looks.

Verdict: FAIL (flag) when the survival rate exceeds
``config.mutation_survival_threshold``. This layer flags *fragile passes*
rather than observing bugs directly — pair it with the unit layer.
"""
from __future__ import annotations

import ast
import copy

from .. import sandbox
from ..tasks import Task
from . import FAIL, PASS, SKIP, LayerResult

_CMP_SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.Gt: ast.GtE}
_BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add}
_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


def _mutation_sites(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    """Enumerate (kind, node) pairs where a first-order mutation applies."""
    sites: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and type(node.ops[0]) in _CMP_SWAP:
            sites.append(("cmp", node))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            sites.append(("bin", node))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_SWAP:
            sites.append(("bool", node))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            sites.append(("int", node))
    return sites


def _apply(kind: str, node: ast.AST) -> None:
    if kind == "cmp":
        node.ops[0] = _CMP_SWAP[type(node.ops[0])]()
    elif kind == "bin":
        node.op = _BIN_SWAP[type(node.op)]()
    elif kind == "bool":
        node.op = _BOOL_SWAP[type(node.op)]()
    elif kind == "int":
        node.value = node.value + 1


def generate_mutants(code: str, max_mutants: int = 6) -> list[str]:
    """Return up to max_mutants single-mutation variants of code (deterministic order)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    n_sites = len(_mutation_sites(tree))
    mutants: list[str] = []
    for i in range(min(n_sites, max_mutants)):
        clone = copy.deepcopy(tree)
        kind, node = _mutation_sites(clone)[i]
        _apply(kind, node)
        try:
            mutants.append(ast.unparse(clone) + "\n")
        except Exception:  # pragma: no cover - unparse of exotic nodes
            continue
    return mutants


def run(code: str, task: Task, config) -> LayerResult:
    mutants = generate_mutants(code, max_mutants=config.max_mutants)
    if not mutants:
        return LayerResult("mutation", SKIP, "no mutation sites (or unparsable code)")

    checks = "\n\n".join(task.tests + task.edge_tests)
    survivors = 0
    for mutant in mutants:
        result = sandbox.run_solution_with_checks(mutant, checks, timeout_s=config.timeout_s)
        if result.ok:
            survivors += 1

    rate = survivors / len(mutants)
    extra = {"mutants": len(mutants), "survivors": survivors, "survival_rate": round(rate, 3)}
    detail = f"{survivors}/{len(mutants)} mutants survived the reference tests"
    if rate > config.mutation_survival_threshold:
        return LayerResult("mutation", FAIL, detail + " — tests too weak to trust", extra)
    return LayerResult("mutation", PASS, detail, extra)
