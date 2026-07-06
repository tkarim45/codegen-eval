"""Solution generation — one code artifact per (task, strategy).

Backends:

  * MockGenerator    — deterministic, key-free. Returns canned solutions from
                       data/mock_solutions/, some with KNOWN seeded failures
                       (ground truth in manifest.json). This is what makes the
                       harness scoring testable offline.
  * ClaudeGenerator  — real Claude via the first-party API (ANTHROPIC_API_KEY).
  * BedrockGenerator — real Claude on AWS Bedrock (AWS creds in env / .env).

Real backends run at temperature 0 and are optional extras — the package
imports and the mock path work without the anthropic SDK installed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import API_MODEL, BEDROCK_MODEL, CALLS_PER_STRATEGY, COST_PER_1M, TEMPERATURE
from .strategies import build_prompt, build_review_prompt, system_prompt
from .tasks import Task

# Load .env if present (API keys / model overrides) — best-effort, never fatal.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass


@dataclass
class Generation:
    task_id: str
    strategy: str
    code: str
    n_calls: int
    est_tokens: int
    cost_usd: float
    # Ground truth, mock mode only. Real generations have unknown failures —
    # that is exactly what the battery is for.
    seeded_failures: list[str] = field(default_factory=list)


def _est_tokens(*texts: str) -> int:
    # ~4 chars/token heuristic; good enough for the relative cost comparison.
    return sum(max(1, len(t) // 4) for t in texts)


class MockGenerator:
    """Deterministic canned solutions with known seeded failures."""

    def __init__(self, data_dir: Path, tier: str = "small"):
        self._dir = data_dir / "mock_solutions"
        self._tier = tier
        self._manifest = json.loads((self._dir / "manifest.json").read_text())

    def generate(self, task: Task, strategy: str) -> Generation:
        entry = self._manifest[task.id][strategy]
        code = (self._dir / entry["file"]).read_text()
        prompt = build_prompt(task, strategy)
        n_calls = CALLS_PER_STRATEGY[strategy]
        # self-review's second call re-sends the draft -> roughly double the tokens.
        est = _est_tokens(prompt, code) * n_calls
        return Generation(
            task_id=task.id,
            strategy=strategy,
            code=code,
            n_calls=n_calls,
            est_tokens=est,
            cost_usd=est / 1_000_000 * COST_PER_1M[self._tier],
            seeded_failures=list(entry["seeded_failures"]),
        )


class _AnthropicBase:
    """Shared logic for the real backends. Subclasses set self._client/_model."""

    _client = None
    _model: str = ""
    _tier: str = "small"

    def generate(self, task: Task, strategy: str) -> Generation:
        prompt = build_prompt(task, strategy)
        code, tokens = self._ask(prompt)
        n_calls = 1
        if strategy == "self-review":
            review = build_review_prompt(task, code)
            code, more = self._ask(review)
            tokens += more
            n_calls = 2
        return Generation(
            task_id=task.id,
            strategy=strategy,
            code=code,
            n_calls=n_calls,
            est_tokens=tokens,
            cost_usd=tokens / 1_000_000 * COST_PER_1M[self._tier],
            seeded_failures=[],  # unknown for real generations
        )

    def _ask(self, prompt: str) -> tuple[str, int]:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=TEMPERATURE,
            system=system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        tokens = msg.usage.input_tokens + msg.usage.output_tokens
        return extract_code(text), tokens


class ClaudeGenerator(_AnthropicBase):
    """First-party Anthropic API. Requires: pip install 'codegen-eval[claude]'."""

    def __init__(self, tier: str = "small"):
        import anthropic  # optional extra — imported lazily

        self._client = anthropic.Anthropic()
        self._model = API_MODEL[tier]
        self._tier = tier


class BedrockGenerator(_AnthropicBase):
    """Claude on AWS Bedrock. Requires: pip install 'codegen-eval[bedrock]'."""

    def __init__(self, tier: str = "small"):
        import anthropic  # optional extra — imported lazily

        self._client = anthropic.AnthropicBedrock()
        self._model = BEDROCK_MODEL[tier]
        self._tier = tier


def get_generator(mode: str, data_dir: Path, tier: str = "small"):
    if mode == "mock":
        return MockGenerator(data_dir, tier=tier)
    if mode == "claude":
        return ClaudeGenerator(tier=tier)
    if mode == "bedrock":
        return BedrockGenerator(tier=tier)
    raise ValueError(f"unknown mode: {mode!r}")


_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the (last) fenced code block out of a model reply, else the raw text."""
    blocks = _CODE_BLOCK.findall(text)
    return (blocks[-1] if blocks else text).strip() + "\n"
