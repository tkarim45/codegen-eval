"""Verification battery — independently toggleable layers.

Each layer exposes ``run(code, task, config) -> LayerResult``. A layer
"catches" a solution when its verdict is FAIL. The scoring joins layer
verdicts with the mock corpus's ground-truth seeded failures to build the
strategy x layer x failure-class catch-rate matrix.

Layers:
    unit        run the task's reference + edge + timed perf tests in the sandbox
    props       deterministic property checks (seeded RNG; hypothesis-style)
    mutation    tiny built-in AST mutator — flags fragile "green" solutions
    lint        static/security lint: bandit + ruff if installed, plus a
                built-in insecure-pattern scanner (always on)
    llm_review  LLM cross-review (stub — skipped in mock mode)
"""
from __future__ import annotations

from dataclasses import dataclass, field

PASS = "pass"
FAIL = "fail"
SKIP = "skipped"


@dataclass
class LayerResult:
    layer: str
    verdict: str  # pass | fail | skipped
    details: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def caught(self) -> bool:
        return self.verdict == FAIL


def get_layers() -> dict:
    """Name -> run callable for every battery layer."""
    from . import lint, llm_review, mutation, props, unit

    return {
        "unit": unit.run,
        "props": props.run,
        "mutation": mutation.run,
        "lint": lint.run,
        "llm_review": llm_review.run,
    }
