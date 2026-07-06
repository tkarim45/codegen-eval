"""CLI — `codegen-eval run --mock` and `codegen-eval report`.

run    generate solutions per strategy, push each through the battery,
       write results.json, print the scorecard
report re-render the scorecard from an existing results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .battery import get_layers
from .config import LAYERS, STRATEGIES, RunConfig
from .generate import get_generator
from .score import EvalRecord, render_report, score
from .tasks import load_tasks


def run_eval(config: RunConfig, verbose: bool = True) -> list[EvalRecord]:
    """The pipeline: tasks -> generate (per strategy) -> battery -> records."""
    tasks = load_tasks(config.data_dir, config.task_ids)
    generator = get_generator(config.mode, config.data_dir, tier=config.model_tier)
    layers = {name: fn for name, fn in get_layers().items() if name in config.layers}

    records: list[EvalRecord] = []
    for task in tasks:
        for strategy in config.strategies:
            gen = generator.generate(task, strategy)
            verdicts: dict[str, str] = {}
            for name, layer_fn in layers.items():
                result = layer_fn(gen.code, task, config)
                verdicts[name] = result.verdict
            records.append(
                EvalRecord(
                    task_id=task.id,
                    strategy=strategy,
                    seeded_failures=gen.seeded_failures,
                    layer_verdicts=verdicts,
                    cost_usd=gen.cost_usd,
                    n_calls=gen.n_calls,
                )
            )
            if verbose:
                flagged = [n for n, v in verdicts.items() if v == "fail"]
                seeded = ",".join(gen.seeded_failures) or "clean"
                caught = ",".join(flagged) or "none"
                print(f"  {task.id:16s} {strategy:12s} seeded={seeded:20s} flagged-by={caught}")
    return records


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.mock and args.mode == "mock":
        print(
            "note: defaulting to --mock (deterministic, key-free). "
            "Use --mode claude|bedrock for real generation.",
            file=sys.stderr,
        )
    mode = "mock" if args.mock else args.mode
    config = RunConfig(
        mode=mode,
        strategies=args.strategies,
        layers=args.layers,
        task_ids=args.tasks,
        seed=args.seed,
        max_mutants=args.max_mutants,
    )
    print(f"codegen-eval: mode={config.mode} tasks={config.task_ids or 'all'}")
    records = run_eval(config)

    out = Path(args.out)
    out.write_text(json.dumps([r.to_dict() for r in records], indent=2) + "\n")
    print(f"\nwrote {len(records)} records -> {out}\n")
    print(render_report(score(records)))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    path = Path(args.results)
    if not path.exists():
        print(f"error: {path} not found — run `codegen-eval run --mock` first", file=sys.stderr)
        return 1
    records = [EvalRecord.from_dict(d) for d in json.loads(path.read_text())]
    print(render_report(score(records)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codegen-eval",
        description="Eval harness for AI-generated code: which prompting and "
        "verification strategies catch which classes of AI-code failure?",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the pipeline and write results.json")
    p_run.add_argument("--mock", action="store_true", help="deterministic key-free mock mode")
    p_run.add_argument("--mode", choices=["mock", "claude", "bedrock"], default="mock")
    p_run.add_argument("--strategies", nargs="+", default=list(STRATEGIES), choices=STRATEGIES)
    p_run.add_argument("--layers", nargs="+", default=list(LAYERS), choices=LAYERS)
    p_run.add_argument("--tasks", nargs="+", default=None, help="subset of task ids")
    p_run.add_argument("--out", default="results.json")
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--max-mutants", type=int, default=6)
    p_run.set_defaults(func=_cmd_run)

    p_rep = sub.add_parser("report", help="re-render the scorecard from results.json")
    p_rep.add_argument("results", nargs="?", default="results.json")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
