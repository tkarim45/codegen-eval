# codegen-eval

**An eval harness for AI-generated code — the AI-assisted interview format, as a repo.**

Interviews changed. Meta moved to AI-assisted coding interviews (announced for late 2025),
where candidates drive an AI assistant and are judged on how they verify its output. Google
added an AI-comprehension round around Gemini-generated code. Canva now expects candidates
to use AI tools and grades the judgment layered on top. The skill being tested is no longer
"can you write a binary search" — it's **"can you tell when the AI's binary search is
wrong, insecure, or quadratic."**

This repo turns that skill into a benchmarkable artifact. It answers one question:

> **Which prompting and verification strategies catch which classes of AI-code failure?**

## How it works

```
coding task ──► LLM generates a solution ──► verification battery ──► catch-rate matrix
                under a PROMPT STRATEGY       (each layer toggleable)     per strategy × layer
                                                                          × failure class
```

**Prompt strategies** (how much context the model gets):

| Strategy | What the model sees | Calls |
|---|---|---|
| `bare` | task description only | 1 |
| `spec` | task + explicit constraints and edge cases | 1 |
| `test-first` | task + the actual unit tests it must pass | 1 |
| `self-review` | generate → model critiques and revises its own code | 2 (≈2× cost) |

**Verification battery** (each layer independently toggleable):

| Layer | What it does | Aimed at |
|---|---|---|
| `unit` | task's reference + edge + timed perf tests, sandboxed | wrong-logic, missed-edge-case, performance-trap |
| `props` | property checks over seeded-RNG random inputs | missed-edge-case, silent-type-error |
| `mutation` | built-in AST mutator; flags green runs whose tests kill few mutants | fragile passes |
| `lint` | built-in insecure-pattern scanner (always on) + bandit + ruff `--select S` when installed | insecure-pattern |
| `llm_review` | LLM cross-review — **stub**, skipped in mock mode | everything tests can't see |

**Failure taxonomy** (what gets seeded and scored): `wrong-logic`, `missed-edge-case`,
`insecure-pattern` (eval / shell-injection / subprocess-shell), `silent-type-error`,
`performance-trap`.

**Mock-first:** `codegen-eval run --mock` is deterministic and key-free. The mock "LLM"
returns canned solutions for all 10 tasks × 4 strategies — 14 of them with *known* seeded
failures from the taxonomy (ground truth in `data/mock_solutions/manifest.json`), on a
designed gradient: `bare` ships 10 bugs, `spec` 3, `test-first` 1 (it still calls `eval()`
— the shown tests are all functional, so they can't see it), `self-review` 0. That makes
the harness's own scoring testable offline. Real Claude / AWS Bedrock generation are
optional extras, always at temperature 0.

**Sandboxing:** generated code runs in a subprocess (`python -I`, wall-clock timeout, temp
cwd, interactive builtins stripped). This is best-effort isolation for benchmark hygiene —
**not a security boundary**. Run genuinely untrusted code in a container/VM.

## Quickstart

```bash
pip install -e ".[dev]"

codegen-eval run --mock              # full pipeline, offline, deterministic
codegen-eval report results.json     # re-render the scorecard

# slices
codegen-eval run --mock --strategies bare self-review --layers unit lint
codegen-eval run --mock --tasks safe_calc list_files

# real models (optional extras; keys via .env — see .env.example)
pip install -e ".[claude]"    # ANTHROPIC_API_KEY
pip install -e ".[bedrock]"   # AWS credentials
codegen-eval run --mode claude
```

## Results

> **TBD — benchmark not yet run.** This is a scaffold: the harness, tasks, mock corpus and
> scoring are in place and tested; the tables below will be filled from real runs and
> committed `results.json` files. Numbers are never hand-written here.

Catch-rate matrix (layer × failure class):

| | wrong-logic | missed-edge-case | insecure-pattern | silent-type-error | performance-trap |
|---|---|---|---|---|---|
| unit | TBD | TBD | TBD | TBD | TBD |
| props | TBD | TBD | TBD | TBD | TBD |
| mutation | TBD | TBD | TBD | TBD | TBD |
| lint | TBD | TBD | TBD | TBD | TBD |
| llm_review | TBD | TBD | TBD | TBD | TBD |

Cost per caught bug (per strategy):

| Strategy | Seeded bugs | Caught | Gen cost | $/caught bug |
|---|---|---|---|---|
| bare | TBD | TBD | TBD | TBD |
| spec | TBD | TBD | TBD | TBD |
| test-first | TBD | TBD | TBD | TBD |
| self-review | TBD | TBD | TBD | TBD |

## Honest findings

> **TBD — pending the first real benchmark run.** One structural observation is already
> baked into the mock corpus by construction (and is the hypothesis to test for real):
> functional verification cannot see security. The `test-first` mock solution for
> `safe_calc` passes every shown test and still calls `eval()` on untrusted input — only
> the lint layer flags it. Whether real models reproduce that pattern is exactly what the
> benchmark will measure.

## The tasks

10 small, real coding tasks in `src/codegeneval/data/tasks/`, each with basic reference
tests, edge-case tests, and (where relevant) seeded-RNG property checks and a timed
performance test: `fizzbuzz`, `is_palindrome`, `binary_search`, `safe_calc` (untrusted
arithmetic eval), `word_count`, `flatten`, `list_files` (untrusted path), `moving_average`,
`slugify`, `has_duplicates` (must be O(n) at 60k elements).

## Roadmap

- [x] Task registry — 10 tasks with reference + edge + property + perf tests
- [x] Prompt strategies: bare / spec / test-first / self-review
- [x] Mock generator with ground-truth seeded failures (all 5 taxonomy classes)
- [x] Sandboxed subprocess execution with timeout
- [x] Battery: unit, props (seeded-RNG), mutation (built-in AST mutator), lint (builtin + bandit/ruff)
- [x] Catch-rate matrix + false-flag rate + cost-per-caught-bug scoring
- [x] CLI (`run --mock`, `report`), tests, CI (pytest + mock smoke run)
- [ ] Real-model benchmark run (Claude API / Bedrock) → fill the results tables
- [ ] `llm_review` layer: independent cross-model reviewer with structured per-class verdicts
- [ ] hypothesis-native property strategies (current checks are seeded-RNG)
- [ ] mutmut comparison run vs the built-in mutator
- [ ] More tasks: concurrency, date/timezone handling, regex-based parsing

## License

MIT © 2026 Taimour Abdul Karim
