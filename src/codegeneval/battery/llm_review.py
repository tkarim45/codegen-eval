"""LLM cross-review layer — STUB.

Design (roadmap): a second, independent model reviews the generated solution
against the task description and the failure taxonomy, returning a structured
verdict per failure class. "Cross" matters: the reviewer must not be the
generator, or it re-approves its own blind spots (the safe_calc test-first
case — functional tests all green, eval() still in the code — is exactly what
this layer exists to catch when lint's pattern list runs out).

Mock mode: always SKIPPED so offline runs stay key-free and deterministic.
Real mode: not yet implemented — returns SKIPPED with an explanatory note
rather than pretending to review.
"""
from __future__ import annotations

from ..tasks import Task
from . import SKIP, LayerResult

REVIEW_PROMPT_TEMPLATE = """\
You are a strict code reviewer. Review the following solution to the task.

Task: {description}

```python
{code}
```

For each category — wrong-logic, missed-edge-case, insecure-pattern,
silent-type-error, performance-trap — answer PASS or FAIL with one line of
justification. Output one `category: verdict — reason` line per category.
"""


def run(code: str, task: Task, config) -> LayerResult:
    if config.mode == "mock":
        return LayerResult("llm_review", SKIP, "stub — skipped in mock mode (key-free)")
    return LayerResult(
        "llm_review",
        SKIP,
        "stub — real cross-review not implemented yet (see module docstring)",
    )
