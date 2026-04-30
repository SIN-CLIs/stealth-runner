"""Stealth-Scoring nach 6 Prüfvektoren mit gewichteten Thresholds."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class StealthResult:
    vector: str; score: float; weight: float; status: str; detail: str = ""

DEFAULT_VECTORS: dict[str, float] = {"tls_ja4": 0.25, "webgl_canvas": 0.20, "navigator": 0.15, "behavior_entropy": 0.20, "locale_timezone": 0.10, "headless_indicators": 0.10}

def calculate_stealth_score(results: list[StealthResult]) -> dict:
    if not results: return {"total_score": 100, "status": "pass", "vectors": []}
    total = sum(r.score * r.weight for r in results)
    status = "pass" if total >= 85 else "warn" if total >= 70 else "fail"
    return {"total_score": round(total, 1), "status": status, "vectors": [{"vector": r.vector, "score": r.score, "status": r.status, "detail": r.detail} for r in results]}
