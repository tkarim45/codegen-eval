"""Failure taxonomy for AI-generated code.

Five classes of failure the harness seeds (in mock mode) and scores against.
Every seeded failure in data/mock_solutions/manifest.json uses one of these ids.
"""
from __future__ import annotations

WRONG_LOGIC = "wrong-logic"
MISSED_EDGE_CASE = "missed-edge-case"
INSECURE_PATTERN = "insecure-pattern"
SILENT_TYPE_ERROR = "silent-type-error"
PERFORMANCE_TRAP = "performance-trap"

FAILURE_CLASSES: list[str] = [
    WRONG_LOGIC,
    MISSED_EDGE_CASE,
    INSECURE_PATTERN,
    SILENT_TYPE_ERROR,
    PERFORMANCE_TRAP,
]

DESCRIPTIONS: dict[str, str] = {
    WRONG_LOGIC: "Core algorithm is wrong on ordinary inputs (off-by-one, wrong branch order).",
    MISSED_EDGE_CASE: "Correct on the happy path, wrong or crashing on boundary inputs "
    "(empty input, zero-size window, punctuation).",
    INSECURE_PATTERN: "Dangerous construct on untrusted input: eval/exec, shell=True with "
    "string interpolation, os.system, pickle.loads.",
    SILENT_TYPE_ERROR: "Returns the wrong type without raising (None fall-through, string "
    "treated as an iterable of characters).",
    PERFORMANCE_TRAP: "Functionally correct but asymptotically wrong (O(n^2) where O(n) is "
    "required) — passes small tests, times out at scale.",
}


def validate(classes: list[str]) -> None:
    """Raise ValueError if any class id is not part of the taxonomy."""
    unknown = [c for c in classes if c not in FAILURE_CLASSES]
    if unknown:
        raise ValueError(f"unknown failure class(es): {unknown}; known: {FAILURE_CLASSES}")
