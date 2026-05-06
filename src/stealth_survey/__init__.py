"""stealth_survey — Ultra-fast survey automation with Nemotron 3 Omni + CDP WebSocket.

Architecture:
    Compact Snapshot → Nemotron Decision → Batch Execute → Memory/Guardian → Loop

Dependencies:
    - NVIDIA NIM API (Nemotron 3 Omni)
    - Chrome CDP WebSocket (port 9999)
    - stealth-memory / stealth-guardian (optional)
"""

from .nim_client import NIMSurveyClient
from .survey_agent import SurveyAgent
from .compact_snapshot import CompactSnapshotGenerator
from .batch_executor import BatchExecutor

__all__ = [
    "SurveyAgent",
    "NIMSurveyClient", 
    "CompactSnapshotGenerator",
    "BatchExecutor",
]
