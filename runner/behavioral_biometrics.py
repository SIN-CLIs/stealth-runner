"""Behavioral Biometrics via scipy.stats PDFs."""
from __future__ import annotations
import numpy as np
from scipy import stats

DWELL_TIME_DIST = stats.gamma(a=5, scale=200)
FLIGHT_TIME_DIST = stats.norm(loc=400, scale=100)
TYPING_DIST = stats.norm(loc=180, scale=40)

def sample_dwell_time() -> float: return max(50, DWELL_TIME_DIST.rvs())/1000.0
def sample_flight_time() -> float: return max(20, FLIGHT_TIME_DIST.rvs())/1000.0
def sample_typing_speed() -> float: return max(60, TYPING_DIST.rvs())
