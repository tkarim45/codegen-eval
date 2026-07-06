# CLAUDE.md — codegen-eval dev guide

Eval harness for AI-generated code: which prompting and verification strategies catch
which classes of AI-code failure? Pipeline: task → LLM generates a solution under a
**prompt strategy** → solution runs through a **verification battery** → score which
battery layer caught which seeded failure class.

## Commands

```bash
make install                 # pip install -e ".[dev]"   (use a named conda env, never base)
make test                    # pytest -q
make run                     # codegen-eval run --mock  (deterministic, key-free)
codegen-eval run --mock --tasks fizzbuzz safe_calc --layers unit lint
codegen-eval report results.json
```

Local convention: `~/miniconda3/envs/claude/bin/python -m pytest -q` — never conda base.

## Architecture (src/codegeneval/)

- `config.py` — `RunConfig`, cost model (USD/1M tokens, blended), model IDs, temperature 0.
- `tasks.py` — task registry; loads `data/tasks/*.json` (10 real tasks, each with basic
  tests + edge tests + optional seeded-RNG property check + optional timed perf test).
- `strategies.py` — prompt builders: `bare`, `spec`, `test-first`, `self-review` (2 calls).
- `generate.py` — `MockGenerator` (canned solutions from `data/mock_solutions/`, ground-truth
  seeded failures in `manifest.json`), `ClaudeGenerator`/`BedrockGenerator` (optional extras,
  lazy anthropic import).
- `sandbox.py` — subprocess runner: `python -I`, wall-clock timeout, temp cwd, stripped
  interactive builtins. **Best-effort isolation, NOT a security boundary.**
- `battery/` — one module per layer, each `run(code, task, config) -> LayerResult`:
  `unit` (basic/edge/perf sections), `props` (seeded-RNG properties), `mutation` (built-in
  AST mutator, flags fragile passes via survival rate), `lint` (builtin regex scanner always
  on; bandit/ruff when installed), `llm_review` (stub, always skipped).
- `taxonomy.py` — the 5 failure classes: wrong-logic, missed-edge-case, insecure-pattern,
  silent-type-error, performance-trap.
- `score.py` — `EvalRecord` → layer × failure-class catch-rate matrix, false-flag rates,
  cost per caught bug. `render_report()` for plain text.
- `cli.py` — `run_eval()` orchestration + argparse (`run`, `report`).

## Mock corpus invariants (tests enforce these)

- Every task × strategy has a solution file; every seeded failure class is in the taxonomy;
  all five classes are represented.
- Designed gradient: `bare` (10 seeded bugs) > `spec` (3) > `test-first` (1: safe_calc still
  uses eval — functional tests can't see security) > `self-review` (0, clean).
- Everything deterministic: temperature 0, seeded RNG, canned solutions. If you add a task,
  add its JSON, 4 mock solutions, and a manifest entry, and keep `test_tasks_schema.py` green.

## Rules

- NEVER fabricate benchmark numbers in the README — results tables stay "TBD" until a real
  run produces them.
- Mock mode must stay key-free and offline; real backends stay optional extras.
- New battery layers: add module under `battery/`, register in `battery/get_layers()` and
  `config.LAYERS`, degrade gracefully when optional deps are missing.
