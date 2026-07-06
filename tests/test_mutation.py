"""Built-in mutator: mutant generation and the survival-rate verdict."""
from codegeneval.battery import FAIL, PASS, SKIP
from codegeneval.battery.mutation import generate_mutants, run
from codegeneval.config import RunConfig
from codegeneval.tasks import Task


def _task(tests, edge_tests=None):
    return Task(
        id="t",
        title="t",
        description="t",
        function_name="f",
        signature="def f(x):",
        constraints=[],
        edge_cases=[],
        tests=tests,
        edge_tests=edge_tests or [],
        perf_test=None,
        properties=None,
    )


CODE = "def f(x):\n    if x > 0:\n        return x + 1\n    return 0\n"


def test_generates_distinct_valid_mutants():
    mutants = generate_mutants(CODE, max_mutants=6)
    assert mutants, "expected at least one mutation site"
    assert all(m != CODE for m in mutants)
    assert len(set(mutants)) == len(mutants)
    for m in mutants:
        compile(m, "<mutant>", "exec")  # every mutant is valid Python


def test_max_mutants_cap():
    assert len(generate_mutants(CODE, max_mutants=1)) == 1


def test_unparsable_code_yields_no_mutants():
    assert generate_mutants("def broken(:\n") == []


def test_strong_tests_kill_mutants():
    # Tests pin the boundary and both branches -> mutants die -> PASS.
    task = _task(
        tests=[
            "assert f(1) == 2",
            "assert f(5) == 6",
            "assert f(0) == 0",
            "assert f(-3) == 0",
        ]
    )
    config = RunConfig(mode="mock", max_mutants=6, mutation_survival_threshold=0.5)
    result = run(CODE, task, config)
    assert result.verdict == PASS
    assert result.extra["survivors"] < result.extra["mutants"]


def test_weak_tests_are_flagged():
    # A tautological test kills nothing -> full survival -> FAIL flag.
    task = _task(tests=["assert True"])
    config = RunConfig(mode="mock", max_mutants=4, mutation_survival_threshold=0.5)
    result = run(CODE, task, config)
    assert result.verdict == FAIL
    assert result.extra["survivors"] == result.extra["mutants"]


def test_no_mutation_sites_skips():
    task = _task(tests=["assert f('a') == 'a'"])
    config = RunConfig(mode="mock")
    result = run("def f(x):\n    return x\n", task, config)
    assert result.verdict == SKIP
