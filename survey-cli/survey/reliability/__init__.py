"""
Reliability package — Production-grade primitives for 24/7 operation.

SR-152: Retry policy, DLQ, and persona contradiction detection.

Exports:
    - RetryPolicy, Retryability, TransientError, PermanentError, FatalError
    - DLQ, DLQRecord
    - ContradictionDetector, Contradiction, PinnedAnswer, IdentityCategory
"""

from .retry_policy import (
    RetryPolicy,
    RetryContext,
    Retryability,
    TransientError,
    PermanentError,
    FatalError,
    default_classify,
)
from .dlq import (
    DLQ,
    DLQRecord,
    DEFAULT_DLQ_PATH,
)
from .contradiction import (
    ContradictionDetector,
    Contradiction,
    PinnedAnswer,
    IdentityCategory,
)

__all__ = [
    # retry_policy
    "RetryPolicy",
    "RetryContext",
    "Retryability",
    "TransientError",
    "PermanentError",
    "FatalError",
    "default_classify",
    # dlq
    "DLQ",
    "DLQRecord",
    "DEFAULT_DLQ_PATH",
    # contradiction
    "ContradictionDetector",
    "Contradiction",
    "PinnedAnswer",
    "IdentityCategory",
]
