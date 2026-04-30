"""Property-based Tests für Exit-Code-Handling."""
from __future__ import annotations
import pytest
from hypothesis import assume, given, strategies as st
from runner.state_machine_extended import ExtendedState, EXIT_CODE_ROUTING

class TestExitCodeRouting:
    def test_success_routes_to_verify(self) -> None: assert EXIT_CODE_ROUTING[0] == ExtendedState.VERIFY
    def test_retryable_routes_to_vision_retry(self) -> None: assert EXIT_CODE_ROUTING[1] == ExtendedState.VISION_RETRY
    def test_fatal_routes_to_recovery(self) -> None: assert EXIT_CODE_ROUTING[2] == ExtendedState.RECOVERY
    def test_stealth_degraded(self) -> None: assert EXIT_CODE_ROUTING[3] == ExtendedState.STEALTH_DEGRADED
    def test_all_states_unique(self) -> None:
        values = [s.value for s in ExtendedState]; assert len(values) == len(set(values))
    def test_new_states_exist(self) -> None:
        assert hasattr(ExtendedState, "VISION_RETRY") and hasattr(ExtendedState, "STEALTH_DEGRADED")

    @given(st.integers(min_value=4, max_value=255))
    def test_unknown_exit_codes_not_routed(self, code: int) -> None:
        assume(code not in {0, 1, 2, 3}); assert code not in EXIT_CODE_ROUTING
