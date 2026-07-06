"""Shipped data integrity: task schema, mock corpus coverage, taxonomy validity."""
import json

import pytest

from codegeneval.config import DATA_DIR, STRATEGIES
from codegeneval.taxonomy import FAILURE_CLASSES
from codegeneval.tasks import load_tasks

TASKS = load_tasks()
MANIFEST = json.loads((DATA_DIR / "mock_solutions" / "manifest.json").read_text())


def test_ships_8_to_10_tasks():
    assert 8 <= len(TASKS) <= 10


def test_task_ids_unique_and_match_filenames():
    ids = [t.id for t in TASKS]
    assert len(ids) == len(set(ids))
    filenames = {p.stem for p in (DATA_DIR / "tasks").glob("*.json")}
    assert set(ids) == filenames


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_task_schema(task):
    assert task.title and task.description
    assert task.function_name in task.signature
    assert task.signature.startswith("def ")
    assert task.constraints and all(isinstance(c, str) for c in task.constraints)
    assert task.edge_cases
    assert task.tests, "every task needs basic reference tests"
    assert task.edge_tests, "every task needs edge-case tests"
    for snippet in task.tests + task.edge_tests:
        compile(snippet, "<test>", "exec")  # snippets are valid Python
    if task.perf_test is not None:
        assert set(task.perf_test) == {"code", "timeout_s"}
        assert task.perf_test["timeout_s"] > 0
        compile(task.perf_test["code"], "<perf>", "exec")
    if task.properties is not None:
        code = task.property_code
        assert "def property_check(fn, rng):" in code
        compile(code, "<props>", "exec")


def test_manifest_covers_every_task_and_strategy():
    assert set(MANIFEST) == {t.id for t in TASKS}
    for task_id, per_strategy in MANIFEST.items():
        assert set(per_strategy) == set(STRATEGIES), task_id


@pytest.mark.parametrize("task_id", sorted(MANIFEST))
def test_mock_solutions_exist_and_compile(task_id):
    for strategy, entry in MANIFEST[task_id].items():
        path = DATA_DIR / "mock_solutions" / entry["file"]
        assert path.exists(), f"{task_id}/{strategy}: missing {entry['file']}"
        compile(path.read_text(), str(path), "exec")


def test_seeded_failures_use_the_taxonomy():
    for task_id, per_strategy in MANIFEST.items():
        for strategy, entry in per_strategy.items():
            for cls in entry["seeded_failures"]:
                assert cls in FAILURE_CLASSES, f"{task_id}/{strategy}: unknown class {cls}"


def test_mock_corpus_seeds_every_failure_class():
    seeded = {
        cls
        for per_strategy in MANIFEST.values()
        for entry in per_strategy.values()
        for cls in entry["seeded_failures"]
    }
    assert seeded == set(FAILURE_CLASSES), "every taxonomy class must be represented"


def test_bare_is_buggiest_and_self_review_clean():
    """The mock corpus's designed gradient: bare >> spec > test-first > self-review."""

    def n_seeded(strategy):
        return sum(len(MANIFEST[t][strategy]["seeded_failures"]) for t in MANIFEST)

    assert n_seeded("bare") > n_seeded("spec") > n_seeded("test-first") >= n_seeded("self-review")
    assert n_seeded("self-review") == 0
