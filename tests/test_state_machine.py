import pytest
from unittest.mock import AsyncMock, patch
from runner.state_machine import SurveyRunner, State
import asyncio

@pytest.mark.asyncio
async def test_state_machine_initializes():
    runner = SurveyRunner("https://test.com")
    assert runner.state == State.IDLE
    assert runner.url == "https://test.com"

@pytest.mark.asyncio  
async def test_state_transition_idle_to_launch():
    runner = SurveyRunner("https://test.com")
    runner.pid = 99999
    await runner._transition()
    assert runner.state == State.CAPTURE

@pytest.mark.asyncio
async def test_max_recoveries_stops():
    runner = SurveyRunner("https://test.com")
    runner.recoveries = 5
    await runner._recover()
    assert runner.state == State.DONE
