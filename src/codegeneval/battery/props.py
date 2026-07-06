"""Property-check layer — invariants over randomly generated inputs.

Each task may ship a ``property_check(fn, rng)`` snippet that asserts
invariants (output length, ordering, round-trips) over inputs drawn from a
SEEDED ``random.Random`` — deterministic across runs, which unit-style
example tests are not designed to be.

If `hypothesis` is installed (dev extra) the layer records that fact; the
shipped property snippets deliberately use the seeded-RNG form so the mock
pipeline stays deterministic and dependency-free. Swapping snippets to
@given-style hypothesis strategies is a roadmap item.
"""
from __future__ import annotations

from .. import sandbox
from ..tasks import Task
from . import FAIL, PASS, SKIP, LayerResult

try:  # optional dev extra — availability is recorded, not required
    import hypothesis  # noqa: F401

    _HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover
    _HAS_HYPOTHESIS = False


def run(code: str, task: Task, config) -> LayerResult:
    prop_code = task.property_code
    if not prop_code:
        return LayerResult("props", SKIP, "task defines no properties")

    check = (
        "import random\n"
        f"_rng = random.Random({config.seed})\n\n"
        f"{prop_code}\n"
        f"property_check({task.function_name}, _rng)\n"
    )
    result = sandbox.run_solution_with_checks(code, check, timeout_s=config.timeout_s)
    extra = {"hypothesis_available": _HAS_HYPOTHESIS}
    if result.ok:
        return LayerResult("props", PASS, "all properties hold", extra)
    return LayerResult("props", FAIL, f"property violated: {result.failure_summary}", extra)
