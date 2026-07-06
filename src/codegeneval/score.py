"""Scoring — turn per-solution layer verdicts into the catch-rate matrix.

Inputs are EvalRecords: one per (task, strategy) with the generation's ground
truth seeded failure classes (mock mode) and every battery layer's verdict.

Outputs:
  * strategy x failure-class seeded counts (how buggy each strategy's output was)
  * layer x failure-class catch-rate matrix (which layer catches which class)
  * per-strategy layer catch rates + false-flag rate on clean solutions
  * cost per caught bug per strategy (generation cost / bugs any layer caught)

A layer "catches" a seeded failure class when its verdict is FAIL on a
solution seeded with that class. A "false flag" is a FAIL verdict on a clean
solution. (The mutation layer flags fragile passes by design, so its false
flags are reported, not hidden.)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .taxonomy import FAILURE_CLASSES


@dataclass
class EvalRecord:
    task_id: str
    strategy: str
    seeded_failures: list[str]  # ground truth (mock); [] = clean
    layer_verdicts: dict[str, str]  # layer -> pass | fail | skipped
    cost_usd: float = 0.0
    n_calls: int = 1

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "strategy": self.strategy,
            "seeded_failures": self.seeded_failures,
            "layer_verdicts": self.layer_verdicts,
            "cost_usd": self.cost_usd,
            "n_calls": self.n_calls,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvalRecord":
        return cls(
            task_id=d["task_id"],
            strategy=d["strategy"],
            seeded_failures=list(d["seeded_failures"]),
            layer_verdicts=dict(d["layer_verdicts"]),
            cost_usd=d.get("cost_usd", 0.0),
            n_calls=d.get("n_calls", 1),
        )


@dataclass
class Scorecard:
    strategies: list[str]
    layers: list[str]
    # layer -> failure class -> (caught, seeded) across all strategies
    layer_class_matrix: dict[str, dict[str, tuple[int, int]]]
    # strategy -> failure class -> seeded count
    strategy_seeded: dict[str, dict[str, int]]
    # strategy -> {seeded_bugs, caught_bugs (any layer), cost_usd, cost_per_caught_bug}
    strategy_summary: dict[str, dict]
    # layer -> (false flags, clean solutions seen)
    false_flags: dict[str, tuple[int, int]] = field(default_factory=dict)


def _rate(caught: int, total: int) -> float | None:
    return None if total == 0 else caught / total


def score(records: list[EvalRecord]) -> Scorecard:
    strategies = sorted({r.strategy for r in records})
    layers = sorted({l for r in records for l in r.layer_verdicts})

    layer_class: dict[str, dict[str, list[int]]] = {
        l: {c: [0, 0] for c in FAILURE_CLASSES} for l in layers
    }
    strategy_seeded: dict[str, dict[str, int]] = {
        s: {c: 0 for c in FAILURE_CLASSES} for s in strategies
    }
    false_flags: dict[str, list[int]] = {l: [0, 0] for l in layers}
    summary: dict[str, dict] = {
        s: {"solutions": 0, "seeded_bugs": 0, "caught_bugs": 0, "cost_usd": 0.0}
        for s in strategies
    }

    for r in records:
        s = summary[r.strategy]
        s["solutions"] += 1
        s["seeded_bugs"] += len(r.seeded_failures)
        s["cost_usd"] += r.cost_usd

        clean = not r.seeded_failures
        any_layer_failed = any(v == "fail" for v in r.layer_verdicts.values())
        if not clean and any_layer_failed:
            s["caught_bugs"] += len(r.seeded_failures)

        for cls in r.seeded_failures:
            strategy_seeded[r.strategy][cls] += 1

        for layer, verdict in r.layer_verdicts.items():
            if clean:
                false_flags[layer][1] += 1
                if verdict == "fail":
                    false_flags[layer][0] += 1
            else:
                for cls in r.seeded_failures:
                    layer_class[layer][cls][1] += 1
                    if verdict == "fail":
                        layer_class[layer][cls][0] += 1

    for s in strategies:
        caught = summary[s]["caught_bugs"]
        cost = summary[s]["cost_usd"]
        summary[s]["cost_per_caught_bug"] = None if caught == 0 else cost / caught

    return Scorecard(
        strategies=strategies,
        layers=layers,
        layer_class_matrix={
            l: {c: (v[0], v[1]) for c, v in classes.items()} for l, classes in layer_class.items()
        },
        strategy_seeded=strategy_seeded,
        strategy_summary=summary,
        false_flags={l: (v[0], v[1]) for l, v in false_flags.items()},
    )


# ---------------------------------------------------------------------------
# Plain-text report rendering
# ---------------------------------------------------------------------------


def _fmt_rate(caught: int, total: int) -> str:
    if total == 0:
        return "  —  "
    return f"{caught}/{total} ({caught / total:4.0%})"


def render_report(card: Scorecard) -> str:
    lines: list[str] = []
    w = 18

    lines.append("== Seeded failures per strategy (mock ground truth) ==")
    header = "strategy".ljust(14) + "".join(c.ljust(w) for c in FAILURE_CLASSES) + "total"
    lines.append(header)
    for s in card.strategies:
        row = card.strategy_seeded[s]
        total = sum(row.values())
        lines.append(
            s.ljust(14) + "".join(str(row[c]).ljust(w) for c in FAILURE_CLASSES) + str(total)
        )

    lines.append("")
    lines.append("== Catch-rate matrix: layer x failure class (caught/seeded) ==")
    lines.append("layer".ljust(14) + "".join(c.ljust(w) for c in FAILURE_CLASSES))
    for layer in card.layers:
        cells = [_fmt_rate(*card.layer_class_matrix[layer][c]).ljust(w) for c in FAILURE_CLASSES]
        lines.append(layer.ljust(14) + "".join(cells))

    lines.append("")
    lines.append("== False flags (layer FAILed on a clean solution) ==")
    for layer in card.layers:
        ff, seen = card.false_flags.get(layer, (0, 0))
        lines.append(f"  {layer.ljust(12)} {_fmt_rate(ff, seen)}")

    lines.append("")
    lines.append("== Cost per caught bug (generation cost, mock estimate) ==")
    lines.append(
        "strategy".ljust(14)
        + "solutions".ljust(11)
        + "seeded".ljust(8)
        + "caught".ljust(8)
        + "gen cost".ljust(12)
        + "$/caught bug"
    )
    for s in card.strategies:
        m = card.strategy_summary[s]
        cpb = m["cost_per_caught_bug"]
        lines.append(
            s.ljust(14)
            + str(m["solutions"]).ljust(11)
            + str(m["seeded_bugs"]).ljust(8)
            + str(m["caught_bugs"]).ljust(8)
            + f"${m['cost_usd']:.6f}".ljust(12)
            + ("—" if cpb is None else f"${cpb:.6f}")
        )

    return "\n".join(lines) + "\n"
