"""Episodic memory — Agent-S3 pattern for trajectory reuse.

Every successful captcha solve is persisted to a local SQLite database.
Future solves on the same domain with a similar gap distance can replay
the trajectory with fresh jitter, achieving near-100% first-try success.
"""

from stealth_captcha.memory.experience import ExperienceMemory, TrajectoryRecord

__all__ = ["ExperienceMemory", "TrajectoryRecord"]
