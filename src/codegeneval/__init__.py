"""codegen-eval — an eval harness for AI-generated code.

Which prompting and verification strategies catch which classes of
AI-code failure? Pipeline: coding task -> LLM generates a solution under a
prompt strategy -> the solution runs through a verification battery ->
score which battery layers catch which seeded failure classes.
"""

__version__ = "0.1.0"

from .config import RunConfig  # noqa: F401
from .score import EvalRecord, Scorecard, score  # noqa: F401
from .tasks import Task, load_tasks  # noqa: F401
