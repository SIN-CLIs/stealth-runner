"""
Reliability package — Production-grade primitives for 24/7 operation.

SR-152: Retry policy, DLQ, and persona contradiction detection.
SR-174: Pre-click network gate (composes with SR-169 DOM stability when it lands).

Exports:
    - RetryPolicy, Retryability, TransientError, PermanentError, FatalError
    - DLQ, DLQRecord
    - ContradictionDetector, Contradiction, PinnedAnswer, IdentityCategory
    - wait_for_network_quiet, GateResult, EventEmitter
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
from .network_gate import (
    GateResult,
    EventEmitter,
    wait_for_network_quiet,
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
    # network_gate (SR-174)
    "GateResult",
    "EventEmitter",
    "wait_for_network_quiet",
]
