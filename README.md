# codegen-eval

**An eval harness for AI-generated code, the AI-assisted interview format, as a repo.**

Interviews changed. Meta moved to AI-assisted coding interviews (announced for late 2025),
where candidates drive an AI assistant and are judged on how they verify its output. Google
added an AI-comprehension round around Gemini-generated code. Canva now expects candidates
to use AI tools and grades the judgment layered on top. The skill being tested is no longer
"can you write a binary search", it's **"can you tell when the AI's binary search is
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
| `llm_review` | LLM cross-review, **stub**, skipped in mock mode | everything tests can't see |

**Failure taxonomy** (what gets seeded and scored): `wrong-logic`, `missed-edge-case`,
`insecure-pattern` (eval / shell-injection / subprocess-shell), `silent-type-error`,
`performance-trap`.

**Mock-first:** `codegen-eval run --mock` is deterministic and key-free. The mock "LLM"
returns canned solutions for all 10 tasks × 4 strategies, 14 of them with *known* seeded
failures from the taxonomy (ground truth in `data/mock_solutions/manifest.json`), on a
designed gradient: `bare` ships 10 bugs, `spec` 3, `test-first` 1 (it still calls `eval()`
,  the shown tests are all functional, so they can't see it), `self-review` 0. That makes
the harness's own scoring testable offline. Real Claude / AWS Bedrock generation are
optional extras, always at temperature 0.

**Sandboxing:** generated code runs in a subprocess (`python -I`, wall-clock timeout, temp
cwd, interactive builtins stripped). This is best-effort isolation for benchmark hygiene, 
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

> **Mock mode (deterministic, key-free) over the seeded mock corpus**, the numbers below
> are the harness scoring the **verification battery** against a fixed corpus of canned
> solutions with *known* seeded failures (ground truth in
> `data/mock_solutions/manifest.json`). They measure which battery layer catches which
> seeded failure class, **not** a real model's code quality. Reproduces byte-identically
> with `codegen-eval run --mock` (re-render with `codegen-eval report results.json`).
> **Real-model (AWS Bedrock, Claude Haiku 4.5) generation benchmark: DONE**, see the
> clearly-marked section below (40 real solutions; the battery flagged 4 true defects; the
> mock's seeded `eval()` danger did not occur on the real model).
>
> Environment for this run: `pip install -e ".[dev]"` (pytest, hypothesis, bandit 1.9.4,
> ruff 0.15.20, mutmut). The `lint` layer's builtin insecure-pattern scanner is always on;
> bandit/ruff are used when on `PATH`. **The catch-rate matrix is byte-identical whether or
> not bandit/ruff are on `PATH`**, the builtin scanner alone catches every insecure-pattern
> seed in this corpus, and the external tools only add corroborating finding IDs (e.g.
> `bandit:B307`, `ruff:S307` for `eval`). All layers produced **zero false flags**.

**Catch-rate matrix (layer × failure class), caught / seeded**, reproduces with
`codegen-eval run --mock`:

| | wrong-logic | missed-edge-case | insecure-pattern | silent-type-error | performance-trap |
|---|---|---|---|---|---|
| unit | 3/3 (100%) | 4/4 (100%) | 4/4 (100%) | 2/2 (100%) | 1/1 (100%) |
| props | 3/3 (100%) | 3/4 (75%) | 0/4 (0%) | 1/2 (50%) | 0/1 (0%) |
| mutation | 0/3 (0%) | 0/4 (0%) | 0/4 (0%) | 0/2 (0%) | 0/1 (0%) |
| lint | 0/3 (0%) | 0/4 (0%) | 4/4 (100%) | 0/2 (0%) | 0/1 (0%) |
| llm_review | 0/3 (0%) | 0/4 (0%) | 0/4 (0%) | 0/2 (0%) | 0/1 (0%) |

Seeded failures per strategy (mock ground truth, the designed gradient, `bare` → clean):

| Strategy | wrong-logic | missed-edge-case | insecure-pattern | silent-type-error | performance-trap | total |
|---|---|---|---|---|---|---|
| bare | 3 | 2 | 2 | 2 | 1 | 10 |
| spec | 0 | 2 | 1 | 0 | 0 | 3 |
| test-first | 0 | 0 | 1 | 0 | 0 | 1 |
| self-review | 0 | 0 | 0 | 0 | 0 | 0 |

False flags (a layer FAILing a clean solution): **0 / 26 for every layer** (unit, props,
mutation, lint, llm_review).

Cost per caught bug (per strategy, mock generation-cost estimate at temperature 0), 
reproduces with `codegen-eval run --mock`:

| Strategy | Seeded bugs | Caught (any layer) | Gen cost | $/caught bug |
|---|---|---|---|---|
| bare | 10 | 10 | $0.000778 | $0.000078 |
| spec | 3 | 3 | $0.001345 | $0.000448 |
| test-first | 1 | 1 | $0.001565 | $0.001565 |
| self-review | 0 | 0 | $0.001942 |, |

Every seeded bug in the corpus is caught by at least one layer (10/10, 3/3, 1/1); the
`$/caught bug` climbs left-to-right because each cleaner strategy costs more to generate
(more prompt context; `self-review` is two calls) while seeding fewer bugs to catch.

### Real-model benchmark: AWS Bedrock, Claude Haiku 4.5

> **Real model: AWS Bedrock, Claude Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`,
> region `us-east-1`), **temperature 0**. One run: **40 solutions** (10 tasks × 4 strategies),
> **50 real Bedrock calls** (self-review is 2 calls/task), **19,963 real tokens**, **$0.0160**
> total (repo's blended `$0.80/1M` approximation, *not* billing-grade). **0 generation errors,
> 0 sandbox crashes.** Reproduces with (needs Bedrock creds in `.env`):
>
> ```bash
> set -a; source.env; set +a
> export AWS_REGION=us-east-1
> export BEDROCK_SMALL_MODEL="us.anthropic.claude-haiku-4-5-20251001-v1:0"
> pip install -e ".[dev,bedrock]"
> codegen-eval run --mode bedrock
> ```

Unlike mock mode there is **no seeded ground truth**, the solutions are *generated*, so a
battery `FAIL` is now the harness's real judgment that a solution is defective. (Because the
scorecard has no seeded classes to attribute catches to in real mode, its printed catch-rate
matrix is all `—` and its "false flags" counter is really the raw per-layer `FAIL` count; the
numbers below are read from the per-solution verdicts.) **Every one of the 4 flags below was a
true positive**. I read the generated code for each; none was a benign misfire.

**Real code quality per prompt strategy** (how many of Haiku's 10 solutions the battery
flagged as defective, *this is the real signal the mock could only simulate*):

| Strategy | Solutions flagged | What was wrong | Gen cost (real tokens) |
|---|---|---|---|
| `bare` | **2 / 10** | `moving_average` returns `[]` for `window<=0` instead of raising `ValueError`; `slugify` emits `--` double-hyphens on punctuation+separator mixes | $0.002409 |
| `spec` | **1 / 10** | `safe_calc`, see note (truncation artifact, not a reasoning bug) | $0.003149 |
| `test-first` | **0 / 10** | clean, every shown-test solution passed the full battery | $0.003228 |
| `self-review` | **1 / 10** | `moving_average`, the second pass rewrote the code (sliding-window sum) but **still** returns `[]` for `window<=0`; it did not fix its own spec violation | $0.007185 |

**Which layer caught the real defects** (solutions flagged, out of 40):

| Layer | Real FAILs | What it caught on real Haiku code |
|---|---|---|
| `unit` | **3 / 40** | `moving_average` (bare + self-review) `window<=0` edge test; `safe_calc` spec broken output |
| `props` | **2 / 40** | `slugify` bare `--` bug (**invisible to the shown functional tests**, a seeded-RNG-only catch); `safe_calc` spec broken output |
| `mutation` | 0 / 40 | no fragile-pass flags (18/40 had no mutation sites; the rest killed enough mutants) |
| `lint` | 0 / 40 | **no insecure patterns to find**, see the `safe_calc` inversion below |
| `llm_review` | 0 / 40 | stub, skipped (40/40) |

**The `safe_calc` insecure-pattern story inverts on a real model.** The mock corpus *seeds*
`eval()` into `safe_calc` (the "functional tests can't see security" set-piece). Real Haiku
**never used `eval`/`exec`/shell in any of the 40 solutions**, for `safe_calc` it wrote a
from-scratch recursive-descent arithmetic parser under *all four* strategies. So `lint` fired
**zero** times: the seeded danger simply didn't occur. The real danger was elsewhere, under
the `spec` strategy Haiku's (secure, verbose) parser **exceeded `max_tokens=1024` and was
truncated mid-function**; with no closing code-fence, `extract_code` fell back to the raw reply
(leading ` ```python ` fence included), producing unparseable code that `unit` + `props`
correctly flagged as broken. That is honest real data: the failure was a *token-budget* limit
on a legitimate secure solution, not a reasoning error and not an insecure pattern.

## Honest findings

**Mock mode (deterministic, key-free) over the seeded mock corpus**, reproduces with
`codegen-eval run --mock`. These describe the **verification battery's** behavior on a
fixed seeded corpus, not a real model's output.

- **`unit` is the workhorse, 100% across all five classes** (3/3, 4/4, 4/4, 2/2, 1/1).
  The reason is that the unit battery runs *hidden* edge and timed-perf tests the model
  never saw, so it catches even the seeded `insecure-pattern` and `performance-trap`
  solutions. It is also the only layer that catches `performance-trap` (`has_duplicates`'s
  O(n²) solution times out at 60k elements) and the only reliable catcher of
  `silent-type-error` (2/2 vs props' 1/2).

- **`lint` is the *only other* layer that catches `insecure-pattern`** (4/4; props /
  mutation / llm_review all 0/4 on that class). If you delete the unit layer's adversarial
  edge tests, lint is your only remaining defense against `eval` / `shell=True` / injection.

- **The "functional tests can't see security" story is real but narrower than a one-liner.**
  The `safe_calc` `test-first` solution regex-guards its input and then calls `eval()`. It
  **passes all three *shown* functional tests** (`2 + 3 * 4`, `(1 + 2) / 2`, `-4 + 10`), 
  a model graded only on the tests it was handed looks correct. What catches it is either
  (a) the `lint` layer detecting `eval`, or (b) a *hidden adversarial* edge test the model
  was **not** shown: `safe_calc('2 ** 8')` must be rejected (exponentiation isn't in the
  allowed `+ - * /`), and the permissive `eval` returns `256.0` instead of raising, so the
  hidden `unit` edge test fails too. Net: **the tests you *choose to show* the model can't
  see the vulnerability; it takes a security linter or an adversarial test the model didn't
  get to satisfy.** (So in this corpus insecure-pattern is caught by *both* unit and lint, 
  lint is not the sole catcher, contrary to a naive reading.)

- **`props` overlaps `unit` on logic/edge/type but has real gaps**, 100% wrong-logic,
  75% missed-edge, 50% silent-type, but **0%** on both insecure-pattern and
  performance-trap. Property checks over random arithmetic inputs never exercise the
  malicious-string or the 60k-element cases.

- **`mutation` and `llm_review` caught nothing (0 across the board), and that is honest,
  not a bug.** `llm_review` is a stub, skipped in mock mode by design. `mutation` only
  flags *fragile green passes* (a solution that passes its tests but whose tests kill few
  mutants); no seeded solution in this corpus produced such a flagged run, and it raised
  zero false flags. It earns its keep on *clean* solutions the other layers wave through,
  which this seeded corpus doesn't contain, a real-model run is where it would bite.

**Real-model (AWS Bedrock, Claude Haiku 4.5, temp 0)**, reproduces with the command in the
real-model results section. Now measuring a *real model's* code quality, not a seeded corpus:

- **The prompt-strategy gradient is real, and showing the tests wins.** `test-first` produced
  **0 defective solutions**; `bare` produced **2**. Handing the model the exact tests it must
  pass is the single most effective prompt strategy for real code quality here, it eliminated
  every defect the other strategies shipped.

- **`self-review` is not a guaranteed fix, and here it wasn't one.** On `moving_average` the
  review pass *rewrote* the code (bare → an efficient sliding-window sum) but **kept the same
  `window<=0` spec violation** (returns `[]` instead of raising `ValueError`). It cost **~3×**
  `bare` (2 calls, $0.0072 vs $0.0024) and did not catch its own missed edge case. Self-review
  improved the algorithm and missed the requirement, exactly the failure the *external*
  battery exists to catch.

- **`props` earned its keep on a real bug the shown tests never saw.** `slugify` bare removes
  punctuation *after* collapsing separator runs, so inputs mixing `.`/`!` with `-`/`_` collapse
  to a single hyphen and *then* lose the punctuation between two hyphens, producing `--`. The
  four shown functional tests all pass; only the seeded-RNG property (`'--' not in out`) hits
  the offending input. The mock could only *simulate* a props-only catch; here it happened on a
  real model.

- **The mock's marquee `insecure-pattern` scenario did not occur.** Real Haiku wrote a safe
  from-scratch parser for `safe_calc` under all four strategies, **no `eval`/`exec`/shell in
  any of the 40 solutions**, so `lint` caught nothing. The seeded "AI still calls `eval()`"
  story is a real *risk* the corpus stress-tests, but on this model/task the real failure mode
  was a **truncated secure solution** (`max_tokens=1024` too small for the verbose parser),
  correctly flagged by `unit`/`props` as broken code. Honest inversion: the harness caught a
  real defect, just not the one the mock predicted.

- **Real cost:** 40 solutions / 50 calls / 19,963 tokens / **$0.0160** total at temp 0.
  `test-first` bought a clean sweep for $0.0032; `self-review` spent $0.0072 to ship one
  uncaught bug. Cheapest reliable strategy on this benchmark = **show the tests**, not review.

## The tasks

10 small, real coding tasks in `src/codegeneval/data/tasks/`, each with basic reference
tests, edge-case tests, and (where relevant) seeded-RNG property checks and a timed
performance test: `fizzbuzz`, `is_palindrome`, `binary_search`, `safe_calc` (untrusted
arithmetic eval), `word_count`, `flatten`, `list_files` (untrusted path), `moving_average`,
`slugify`, `has_duplicates` (must be O(n) at 60k elements).

## Roadmap

- [x] Task registry, 10 tasks with reference + edge + property + perf tests
- [x] Prompt strategies: bare / spec / test-first / self-review
- [x] Mock generator with ground-truth seeded failures (all 5 taxonomy classes)
- [x] Sandboxed subprocess execution with timeout
- [x] Battery: unit, props (seeded-RNG), mutation (built-in AST mutator), lint (builtin + bandit/ruff)
- [x] Catch-rate matrix + false-flag rate + cost-per-caught-bug scoring
- [x] CLI (`run --mock`, `report`), tests, CI (pytest + mock smoke run)
- [x] Mock-mode results recorded (deterministic catch-rate matrix + cost table above; 45 tests pass)
- [x] Real-model benchmark run (AWS Bedrock, Claude Haiku 4.5, temp 0) → real-model results section filled: 40 solutions, 4 true defects caught, insecure-pattern seed did not occur on the real model
- [ ] `llm_review` layer: independent cross-model reviewer with structured per-class verdicts
- [ ] hypothesis-native property strategies (current checks are seeded-RNG)
- [ ] mutmut comparison run vs the built-in mutator
- [ ] More tasks: concurrency, date/timezone handling, regex-based parsing

## License

MIT © 2026 Taimour Abdul Karim
