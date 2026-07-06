"""Prompt strategies — how much context the model gets before writing code.

    bare        task description only (the "just vibe it" baseline)
    spec        task + explicit constraints and edge cases spelled out
    test-first  task + the actual unit tests the code must pass
    self-review generate, then a second pass where the model critiques and
                revises its own solution (2 calls -> ~2x generation cost)

These mirror how candidates actually drive AI assistants in AI-assisted
coding interviews: from a one-line ask to spec-driven prompting to showing
the tests to asking the model to check its own work.
"""
from __future__ import annotations

from .tasks import Task

STRATEGIES = ["bare", "spec", "test-first", "self-review"]

_SYSTEM = (
    "You are an expert Python engineer. Reply with ONLY a Python code block "
    "implementing the requested function. No prose outside the code."
)


def build_prompt(task: Task, strategy: str) -> str:
    """The (first) generation prompt for a task under a strategy."""
    base = f"{task.description}\n\nSignature:\n{task.signature}"

    if strategy == "bare":
        return base

    if strategy == "spec":
        constraints = "\n".join(f"- {c}" for c in task.constraints)
        edges = "\n".join(f"- {e}" for e in task.edge_cases)
        return (
            f"{base}\n\nHard constraints:\n{constraints}\n\n"
            f"Edge cases your code MUST handle:\n{edges}"
        )

    if strategy == "test-first":
        shown = "\n\n".join(task.tests + task.edge_tests)
        return (
            f"{base}\n\nYour implementation must pass ALL of these tests:\n\n"
            f"```python\n{shown}\n```"
        )

    if strategy == "self-review":
        # First call is a bare generation; build_review_prompt drives call two.
        return base

    raise ValueError(f"unknown strategy: {strategy!r}; known: {STRATEGIES}")


def build_review_prompt(task: Task, draft_code: str) -> str:
    """Second call for the self-review strategy: critique and revise the draft."""
    return (
        f"You wrote this solution for the task below.\n\nTask: {task.description}\n\n"
        f"```python\n{draft_code}\n```\n\n"
        "Critique it for logic errors, missed edge cases, insecure patterns "
        "(eval/exec/shell injection), silent type errors, and performance traps. "
        "Then reply with ONLY the corrected final code block."
    )


def system_prompt() -> str:
    return _SYSTEM
