"""Run configuration and the cost model.

Everything is deterministic: temperature 0 everywhere, fixed seed for the
property-check RNG, and mock generation reads canned solutions from disk.

Cost model: USD per 1M tokens (blended input+output approximation), the same
convention as the sibling llm-router repo. These are approximations for the
cost-per-caught-bug comparison, NOT billing-grade numbers — update against
current published pricing before quoting results.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --- model / cost constants -------------------------------------------------

# USD per 1M tokens, blended input+output approximation. Update before real runs.
COST_PER_1M = {"small": 0.80, "large": 15.0}  # haiku-class vs opus-class

# First-party Anthropic API model IDs (real mode).
API_MODEL = {"small": "claude-haiku-4-5-20251001", "large": "claude-opus-4-6"}

# AWS Bedrock inference-profile IDs (repo convention: "global." prefix).
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
BEDROCK_MODEL = {
    "small": os.getenv("BEDROCK_SMALL_MODEL", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
    "large": os.getenv("BEDROCK_LARGE_MODEL", "global.anthropic.claude-opus-4-6-v1"),
}

TEMPERATURE = 0.0  # always — reproducibility over creativity

# --- defaults ---------------------------------------------------------------

STRATEGIES = ["bare", "spec", "test-first", "self-review"]
LAYERS = ["unit", "props", "mutation", "lint", "llm_review"]

# Generation calls per strategy (self-review = generate + critique + revise passes).
CALLS_PER_STRATEGY = {"bare": 1, "spec": 1, "test-first": 1, "self-review": 2}

DATA_DIR = Path(__file__).parent / "data"


@dataclass
class RunConfig:
    """Configuration for one harness run."""

    mode: str = "mock"  # mock | claude | bedrock
    strategies: list[str] = field(default_factory=lambda: list(STRATEGIES))
    layers: list[str] = field(default_factory=lambda: list(LAYERS))
    task_ids: list[str] | None = None  # None = all shipped tasks
    model_tier: str = "small"  # which tier generates code in real mode

    # Sandbox / battery knobs
    timeout_s: float = 5.0  # default per-sandbox-run timeout
    max_mutants: int = 6  # cap for the built-in mutator
    mutation_survival_threshold: float = 0.5  # flag if > this fraction of mutants survive
    seed: int = 0  # property-check RNG seed

    data_dir: Path = field(default_factory=lambda: DATA_DIR)

    def __post_init__(self) -> None:
        if self.mode not in ("mock", "claude", "bedrock"):
            raise ValueError(f"unknown mode: {self.mode!r}")
        unknown = [s for s in self.strategies if s not in STRATEGIES]
        if unknown:
            raise ValueError(f"unknown strategies: {unknown}; known: {STRATEGIES}")
        unknown = [l for l in self.layers if l not in LAYERS]
        if unknown:
            raise ValueError(f"unknown battery layers: {unknown}; known: {LAYERS}")
