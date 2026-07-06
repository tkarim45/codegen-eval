"""Task registry.

Tasks live as JSON files in ``data/tasks/`` inside the package. Each task
ships with basic reference tests, edge-case tests, optional property checks
(deterministic, seeded-RNG driven) and an optional timed performance test.

Schema (validated by tests/test_tasks_schema.py):

    id             str, unique, matches the filename
    title          str
    description    str  — the task prompt shown to the model
    function_name  str  — entry point the tests call
    signature      str  — the expected def line (shown to the model)
    constraints    list[str]  — used by the 'spec' strategy
    edge_cases     list[str]  — used by the 'spec' strategy
    tests          list[str]  — basic reference tests (Python snippets)
    edge_tests     list[str]  — edge-case tests (Python snippets)
    perf_test      {code: str, timeout_s: float} | null
    properties     list[str] | null — lines of a `def property_check(fn, rng)` snippet
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA_DIR

REQUIRED_FIELDS = [
    "id",
    "title",
    "description",
    "function_name",
    "signature",
    "constraints",
    "edge_cases",
    "tests",
    "edge_tests",
    "perf_test",
    "properties",
]


@dataclass
class Task:
    id: str
    title: str
    description: str
    function_name: str
    signature: str
    constraints: list[str]
    edge_cases: list[str]
    tests: list[str]
    edge_tests: list[str]
    perf_test: dict | None = None
    properties: list[str] | None = field(default=None)

    @property
    def property_code(self) -> str | None:
        """The property_check snippet as a single source string."""
        if not self.properties:
            return None
        return "\n".join(self.properties) + "\n"

    @classmethod
    def from_json(cls, path: Path) -> "Task":
        raw = json.loads(path.read_text())
        missing = [f for f in REQUIRED_FIELDS if f not in raw]
        if missing:
            raise ValueError(f"{path.name}: missing task fields: {missing}")
        return cls(**{k: raw[k] for k in REQUIRED_FIELDS})


def load_tasks(data_dir: Path | None = None, task_ids: list[str] | None = None) -> list[Task]:
    """Load all shipped tasks (or the named subset), sorted by id."""
    tasks_dir = (data_dir or DATA_DIR) / "tasks"
    tasks = [Task.from_json(p) for p in sorted(tasks_dir.glob("*.json"))]
    if task_ids is not None:
        by_id = {t.id: t for t in tasks}
        unknown = [t for t in task_ids if t not in by_id]
        if unknown:
            raise ValueError(f"unknown task id(s): {unknown}; known: {sorted(by_id)}")
        tasks = [by_id[t] for t in task_ids]
    if not tasks:
        raise RuntimeError(f"no tasks found in {tasks_dir}")
    return tasks
