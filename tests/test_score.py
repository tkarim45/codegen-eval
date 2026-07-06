"""Scoring math on synthetic records + a fast end-to-end mock slice."""
from codegeneval.cli import run_eval
from codegeneval.config import RunConfig
from codegeneval.score import EvalRecord, render_report, score


def _rec(task, strategy, seeded, verdicts, cost=0.001):
    return EvalRecord(
        task_id=task,
        strategy=strategy,
        seeded_failures=seeded,
        layer_verdicts=verdicts,
        cost_usd=cost,
    )


def test_catch_rate_matrix():
    records = [
        _rec("a", "bare", ["wrong-logic"], {"unit": "fail", "lint": "pass"}),
        _rec("b", "bare", ["wrong-logic"], {"unit": "pass", "lint": "pass"}),
        _rec("c", "bare", ["insecure-pattern"], {"unit": "pass", "lint": "fail"}),
        _rec("d", "spec", [], {"unit": "pass", "lint": "pass"}),
    ]
    card = score(records)

    # unit caught 1 of 2 wrong-logic solutions, 0 of 1 insecure
    assert card.layer_class_matrix["unit"]["wrong-logic"] == (1, 2)
    assert card.layer_class_matrix["unit"]["insecure-pattern"] == (0, 1)
    # lint caught the insecure one, no wrong-logic
    assert card.layer_class_matrix["lint"]["insecure-pattern"] == (1, 1)
    assert card.layer_class_matrix["lint"]["wrong-logic"] == (0, 2)


def test_seeded_counts_and_summary():
    records = [
        _rec("a", "bare", ["wrong-logic", "insecure-pattern"], {"unit": "fail"}, cost=0.002),
        _rec("b", "bare", [], {"unit": "pass"}, cost=0.001),
        _rec("a", "spec", [], {"unit": "pass"}, cost=0.004),
    ]
    card = score(records)
    assert card.strategy_seeded["bare"]["wrong-logic"] == 1
    assert card.strategy_seeded["bare"]["insecure-pattern"] == 1

    bare = card.strategy_summary["bare"]
    assert bare["solutions"] == 2
    assert bare["seeded_bugs"] == 2
    assert bare["caught_bugs"] == 2  # both bugs on the flagged solution count
    assert abs(bare["cost_usd"] - 0.003) < 1e-12
    assert abs(bare["cost_per_caught_bug"] - 0.0015) < 1e-12

    spec = card.strategy_summary["spec"]
    assert spec["seeded_bugs"] == 0
    assert spec["cost_per_caught_bug"] is None  # no division by zero


def test_false_flags_counted_on_clean_solutions_only():
    records = [
        _rec("a", "bare", [], {"unit": "fail", "lint": "pass"}),
        _rec("b", "bare", ["wrong-logic"], {"unit": "fail", "lint": "pass"}),
    ]
    card = score(records)
    assert card.false_flags["unit"] == (1, 1)  # 1 false flag on 1 clean solution
    assert card.false_flags["lint"] == (0, 1)


def test_skipped_verdicts_do_not_catch():
    records = [_rec("a", "bare", ["wrong-logic"], {"llm_review": "skipped"})]
    card = score(records)
    assert card.layer_class_matrix["llm_review"]["wrong-logic"] == (0, 1)
    assert card.strategy_summary["bare"]["caught_bugs"] == 0


def test_render_report_smoke():
    records = [_rec("a", "bare", ["wrong-logic"], {"unit": "fail"})]
    text = render_report(score(records))
    assert "Catch-rate matrix" in text
    assert "wrong-logic" in text
    assert "Cost per caught bug" in text


def test_end_to_end_mock_slice():
    """Real pipeline on a small slice: seeded bugs get caught, clean code passes."""
    config = RunConfig(
        mode="mock",
        strategies=["bare", "self-review"],
        layers=["unit", "lint"],
        task_ids=["fizzbuzz", "safe_calc"],
    )
    records = run_eval(config, verbose=False)
    assert len(records) == 4
    by_key = {(r.task_id, r.strategy): r for r in records}

    # bare fizzbuzz has seeded wrong-logic -> unit catches it
    assert by_key[("fizzbuzz", "bare")].seeded_failures == ["wrong-logic"]
    assert by_key[("fizzbuzz", "bare")].layer_verdicts["unit"] == "fail"

    # bare safe_calc uses eval -> lint catches it even though unit tests pass
    assert by_key[("safe_calc", "bare")].seeded_failures == ["insecure-pattern"]
    assert by_key[("safe_calc", "bare")].layer_verdicts["lint"] == "fail"
    assert by_key[("safe_calc", "bare")].layer_verdicts["unit"] == "fail"  # rejects '2 ** 8' edge

    # self-review solutions are clean and pass both layers
    for task_id in ("fizzbuzz", "safe_calc"):
        rec = by_key[(task_id, "self-review")]
        assert rec.seeded_failures == []
        assert rec.layer_verdicts["unit"] == "pass"
        assert rec.layer_verdicts["lint"] == "pass"

    # self-review costs more than bare (two calls)
    assert by_key[("fizzbuzz", "self-review")].cost_usd > by_key[("fizzbuzz", "bare")].cost_usd
