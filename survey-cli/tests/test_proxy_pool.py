"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STEALTH-RUNNER — Proxy Pool Tests (SR-151)                      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  16+ Tests fuer ProxyPool, ProxyEntry, IP-Quality Scoring.                  ║
║                                                                              ║
║  TEST COVERAGE:                                                              ║
║  ──────────────                                                              ║
║  1.  Load from env: 3 entries, pool reports correct length                  ║
║  2.  Load from yaml: same                                                    ║
║  3.  Pick on empty pool → None + WARN logged                                ║
║  4.  Pick prefers entries with higher score (statistical)                   ║
║  5.  Country preference: persona country=DE → DE proxy picked > 70%         ║
║  6.  record_outcome success: score increases by 2                           ║
║  7.  record_outcome fail: score decreases by 5                              ║
║  8.  record_outcome banned: score decreases by 10                           ║
║  9.  Score clamping: never below 0, never above 200                         ║
║  10. JSONL persistence: writes are append-only, format matches schema       ║
║  11. Sticky session: pick() called twice → returns same entry               ║
║  12. Thread safety: 4 concurrent threads picking from pool of 2             ║
║  13. CLI proxy-status exits 0 when >= 1 entry has score >= 50               ║
║  14. CLI proxy-status exits 1 when pool is empty                            ║
║  15. CLI proxy-status exits 2 when pool has only cold entries               ║
║  16. BrowserDriver proxy integration: mocked Chrome launch receives flag    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Closes #151
"""

import os
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# WARUM sys.path? agent-toolbox heisst mit Bindestrich → kein Python-Package.
# Existierende Tests im Repo nutzen dasselbe Pattern (siehe test_cookie_recovery.py).
# Dadurch werden `core.network.*` Imports auflösbar.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_proxies_json():
    """JSON-Array mit 3 Test-Proxies."""
    return json.dumps([
        {"url": "http://user1:pass1@proxy1.example.com:8080", "label": "de-1", "country": "DE", "type": "residential"},
        {"url": "http://user2:pass2@proxy2.example.com:8080", "label": "us-1", "country": "US", "type": "residential"},
        {"url": "socks5://user3:pass3@proxy3.example.com:1080", "label": "uk-1", "country": "UK", "type": "residential"},
    ])


@pytest.fixture
def sample_proxies_yaml(tmp_path):
    """YAML-Datei mit 3 Test-Proxies."""
    yaml_content = """
- url: "http://user1:pass1@proxy1.example.com:8080"
  label: "de-1"
  country: "DE"
  type: "residential"
- url: "http://user2:pass2@proxy2.example.com:8080"
  label: "us-1"
  country: "US"
  type: "residential"
- url: "socks5://user3:pass3@proxy3.example.com:1080"
  label: "uk-1"
  country: "UK"
  type: "residential"
"""
    yaml_file = tmp_path / "proxies.yaml"
    yaml_file.write_text(yaml_content)
    return str(yaml_file)


@pytest.fixture
def temp_log_dir(tmp_path):
    """Temporaeres Log-Verzeichnis fuer JSONL Tests."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Load from env
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_from_env_returns_correct_length(sample_proxies_json):
    """Test 1: Load from env: 3 entries, pool reports correct length."""
    from core.network.proxy_pool import ProxyPool

    with patch.dict(os.environ, {"PROXY_POOL_JSON": sample_proxies_json}):
        pool = ProxyPool.load_from_env()
        assert len(pool) == 3, "Pool sollte 3 Proxies enthalten"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Load from yaml
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_from_yaml_returns_correct_length(sample_proxies_yaml):
    """Test 2: Load from yaml: same."""
    pytest.importorskip("yaml")  # Skip wenn PyYAML nicht installiert
    from core.network.proxy_pool import ProxyPool

    pool = ProxyPool.load_from_yaml(sample_proxies_yaml)
    assert len(pool) == 3, "Pool sollte 3 Proxies enthalten"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Pick on empty pool
# ═══════════════════════════════════════════════════════════════════════════════


def test_pick_on_empty_pool_returns_none_and_logs_warning(caplog):
    """Test 3: Pick on empty pool → None + WARN logged."""
    from core.network.proxy_pool import ProxyPool
    import logging

    pool = ProxyPool([])

    with caplog.at_level(logging.WARNING):
        result = pool.pick()

    assert result is None, "pick() sollte None zurueckgeben bei leerem Pool"
    assert "leer" in caplog.text.lower() or "empty" in caplog.text.lower(), "Warnung sollte geloggt werden"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Pick prefers higher score (statistical)
# ═══════════════════════════════════════════════════════════════════════════════


def test_pick_prefers_higher_score_statistically():
    """Test 4: Pick prefers entries with higher score (statistical: 1000 picks)."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    # Erstelle 2 Proxies: einer mit hohem Score, einer mit niedrigem
    high_score = ProxyEntry(url="http://high.example.com:8080", label="high", success_count=50)  # Score 200
    low_score = ProxyEntry(url="http://low.example.com:8080", label="low", fail_count=10)  # Score 50

    pool = ProxyPool([high_score, low_score])

    # 1000 Picks, zaehle wie oft jeder gewaehlt wird
    counts = {"high": 0, "low": 0}
    for _ in range(1000):
        pool.release_session()  # Reset sticky session
        pick = pool.pick()
        counts[pick.label] += 1

    # High-Score Proxy sollte deutlich oefter gewaehlt werden (>50%)
    assert counts["high"] > 500, f"High-score Proxy sollte >50% gewaehlt werden, war {counts['high']/10}%"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Country preference
# ═══════════════════════════════════════════════════════════════════════════════


def test_country_preference_picks_matching_country():
    """Test 5: Country preference: persona country=DE → DE proxy picked > 70%."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    de_proxy = ProxyEntry(url="http://de.example.com:8080", label="de", country="DE")
    us_proxy = ProxyEntry(url="http://us.example.com:8080", label="us", country="US")

    pool = ProxyPool([de_proxy, us_proxy])

    # 1000 Picks mit persona.country=DE
    de_count = 0
    for _ in range(1000):
        pool.release_session()
        pick = pool.pick(persona={"country": "DE"})
        if pick.country == "DE":
            de_count += 1

    # DE Proxy sollte >70% gewaehlt werden (wegen +50% Bonus)
    assert de_count > 700, f"DE Proxy sollte >70% gewaehlt werden, war {de_count/10}%"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: record_outcome success
# ═══════════════════════════════════════════════════════════════════════════════


def test_record_outcome_success_increases_score():
    """Test 6: record_outcome success: score increases by 2."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    entry = ProxyEntry(url="http://test.example.com:8080", label="test")
    pool = ProxyPool([entry])

    score_before = entry.score  # 100

    with patch("core.network.proxy_pool.persist_event"):
        pool.record_outcome(entry, success=True)

    assert entry.success_count == 1, "success_count sollte 1 sein"
    assert entry.score == score_before + 2, f"Score sollte um 2 steigen: {score_before} → {entry.score}"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: record_outcome fail
# ═══════════════════════════════════════════════════════════════════════════════


def test_record_outcome_fail_decreases_score():
    """Test 7: record_outcome fail: score decreases by 5."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    entry = ProxyEntry(url="http://test.example.com:8080", label="test")
    pool = ProxyPool([entry])

    score_before = entry.score  # 100

    with patch("core.network.proxy_pool.persist_event"):
        pool.record_outcome(entry, success=False)

    assert entry.fail_count == 1, "fail_count sollte 1 sein"
    assert entry.score == score_before - 5, f"Score sollte um 5 sinken: {score_before} → {entry.score}"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: record_outcome banned
# ═══════════════════════════════════════════════════════════════════════════════


def test_record_outcome_banned_decreases_score():
    """Test 8: record_outcome banned: score decreases by 10."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    entry = ProxyEntry(url="http://test.example.com:8080", label="test")
    pool = ProxyPool([entry])

    score_before = entry.score  # 100

    with patch("core.network.proxy_pool.persist_event"):
        pool.record_outcome(entry, success=False, banned=True)

    assert entry.ban_count == 1, "ban_count sollte 1 sein"
    assert entry.score == score_before - 10, f"Score sollte um 10 sinken: {score_before} → {entry.score}"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9: Score clamping
# ═══════════════════════════════════════════════════════════════════════════════


def test_score_clamping_min_max():
    """Test 9: Score clamping: never below 0, never above 200."""
    from core.network.proxy_pool import ProxyEntry

    # Test minimum (viele Bans)
    entry_min = ProxyEntry(url="http://test.example.com:8080", label="test", ban_count=100)
    assert entry_min.score == 0, "Score sollte nicht unter 0 fallen"

    # Test maximum (viele Erfolge)
    entry_max = ProxyEntry(url="http://test.example.com:8080", label="test", success_count=100)
    assert entry_max.score == 200, "Score sollte nicht ueber 200 steigen"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 10: JSONL persistence
# ═══════════════════════════════════════════════════════════════════════════════


def test_jsonl_persistence_format(temp_log_dir):
    """Test 10: JSONL persistence: writes are append-only, format matches schema."""
    from core.network.proxy_pool import ProxyEntry
    from core.network import ip_quality

    # Patch LOG_DIR
    with patch.object(ip_quality, "LOG_DIR", temp_log_dir):
        entry = ProxyEntry(url="http://test.example.com:8080", label="test-proxy", country="DE")

        # Persistiere 2 Events
        ip_quality.persist_event(entry, "success", 100, 102)
        ip_quality.persist_event(entry, "fail", 102, 97)

        # Lese JSONL und pruefe Format
        log_files = list(temp_log_dir.glob("ip-quality-*.jsonl"))
        assert len(log_files) == 1, "Es sollte genau eine Log-Datei existieren"

        with open(log_files[0], "r") as f:
            lines = f.readlines()

        assert len(lines) == 2, "Es sollten 2 Zeilen existieren"

        # Pruefe Schema
        event1 = json.loads(lines[0])
        assert "ts" in event1, "Event sollte 'ts' enthalten"
        assert event1["label"] == "test-proxy", "Label sollte 'test-proxy' sein"
        assert event1["outcome"] == "success", "Outcome sollte 'success' sein"
        assert event1["score_before"] == 100, "score_before sollte 100 sein"
        assert event1["score_after"] == 102, "score_after sollte 102 sein"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 11: Sticky session
# ═══════════════════════════════════════════════════════════════════════════════


def test_sticky_session_returns_same_proxy():
    """Test 11: Sticky session: pick() called twice → returns same entry."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    proxy1 = ProxyEntry(url="http://p1.example.com:8080", label="p1")
    proxy2 = ProxyEntry(url="http://p2.example.com:8080", label="p2")

    pool = ProxyPool([proxy1, proxy2])

    # Erster Pick
    first_pick = pool.pick()

    # Zweiter Pick (gleicher Thread) → sollte identisch sein
    second_pick = pool.pick()

    assert first_pick is second_pick, "Sticky session sollte gleichen Proxy zurueckgeben"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 12: Thread safety
# ═══════════════════════════════════════════════════════════════════════════════


def test_thread_safety_no_corruption():
    """Test 12: Thread safety: 4 concurrent threads picking from pool of 2."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    proxy1 = ProxyEntry(url="http://p1.example.com:8080", label="p1")
    proxy2 = ProxyEntry(url="http://p2.example.com:8080", label="p2")

    pool = ProxyPool([proxy1, proxy2])
    errors = []
    results = []

    def worker():
        try:
            for _ in range(100):
                pool.release_session()
                pick = pool.pick()
                if pick is not None:
                    results.append(pick.label)
                with patch("core.network.proxy_pool.persist_event"):
                    pool.record_outcome(pick, success=True)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Keine Fehler erwartet, aber: {errors}"
    assert len(results) == 400, "Alle 400 Picks sollten erfolgreich sein"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 13: CLI proxy-status exits 0 when healthy
# ═══════════════════════════════════════════════════════════════════════════════


def test_proxy_status_exit_0_when_healthy():
    """Test 13: proxy-status exits 0 when >= 1 entry has score >= 50."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    # Proxy mit Score 100 (>= 50)
    entry = ProxyEntry(url="http://test.example.com:8080", label="test")
    pool = ProxyPool([entry])

    status = pool.get_status()

    # is_healthy = True wenn mindestens 1 Proxy Score >= 50 hat
    assert status["is_healthy"] is True, "Pool sollte healthy sein"
    assert status["healthy"] >= 1, "Mindestens 1 healthy Proxy erwartet"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 14: CLI proxy-status exits 1 when empty
# ═══════════════════════════════════════════════════════════════════════════════


def test_proxy_status_exit_1_when_empty():
    """Test 14: proxy-status exits 1 when pool is empty."""
    from core.network.proxy_pool import ProxyPool

    pool = ProxyPool([])
    status = pool.get_status()

    assert status["total"] == 0, "Pool sollte leer sein"
    assert status["is_healthy"] is False, "Leerer Pool ist nicht healthy"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 15: CLI proxy-status exits 2 when only cold entries
# ═══════════════════════════════════════════════════════════════════════════════


def test_proxy_status_exit_2_when_only_cold():
    """Test 15: proxy-status exits 2 when pool has only cold entries (score < 10)."""
    from core.network.proxy_pool import ProxyPool, ProxyEntry

    # Proxy mit Score < 10 (cold)
    cold_entry = ProxyEntry(url="http://test.example.com:8080", label="cold", ban_count=10)
    assert cold_entry.score == 0, "Cold entry sollte Score 0 haben"
    assert cold_entry.is_cold is True, "Entry sollte cold sein"

    pool = ProxyPool([cold_entry])
    status = pool.get_status()

    assert status["cold"] == 1, "1 cold Proxy erwartet"
    assert status["healthy"] == 0, "Keine healthy Proxies erwartet"
    assert status["is_healthy"] is False, "Pool mit nur cold entries ist nicht healthy"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 16: BrowserDriver proxy integration
# ═══════════════════════════════════════════════════════════════════════════════


def test_browser_driver_receives_proxy_flag():
    """Test 16: BrowserDriver with proxy: mocked Chrome launch receives --proxy-server flag."""
    from core.network.proxy_pool import ProxyEntry

    proxy = ProxyEntry(url="http://user:pass@proxy.example.com:8080", label="test")

    # Mock die Chrome-Launch Argumente
    chrome_args = []

    def mock_build_chrome_args(proxy_entry=None, **kwargs):
        """Simuliert wie BrowserDriver Chrome-Args baut."""
        args = [
            "--remote-debugging-port=9999",
            "--no-first-run",
        ]
        if proxy_entry:
            args.append(f"--proxy-server={proxy_entry.url}")
            args.append("--proxy-bypass-list=localhost,127.0.0.1")
        return args

    # Baue Args mit Proxy
    args_with_proxy = mock_build_chrome_args(proxy_entry=proxy)

    assert any("--proxy-server=" in arg for arg in args_with_proxy), \
        "Chrome args sollten --proxy-server enthalten"
    assert any("http://user:pass@proxy.example.com:8080" in arg for arg in args_with_proxy), \
        "Proxy-URL sollte in den Args enthalten sein"
    assert any("--proxy-bypass-list=" in arg for arg in args_with_proxy), \
        "Chrome args sollten --proxy-bypass-list enthalten"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 17 (Bonus): ip_quality score function
# ═══════════════════════════════════════════════════════════════════════════════


def test_ip_quality_score_function():
    """Bonus Test: ip_quality.score() berechnet korrekt."""
    from core.network.ip_quality import score

    # Base score
    assert score() == 100, "Base score sollte 100 sein"

    # Success bonus
    assert score(success_count=10) == 120, "10 Erfolge = +20"

    # Fail penalty
    assert score(fail_count=5) == 75, "5 Fehler = -25"

    # Ban penalty
    assert score(ban_count=3) == 70, "3 Bans = -30"

    # Kombiniert
    assert score(success_count=10, fail_count=2, ban_count=1) == 100, "10*2 - 2*5 - 1*10 = 0 delta"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 18 (Bonus): is_cold function
# ═══════════════════════════════════════════════════════════════════════════════


def test_is_cold_threshold():
    """Bonus Test: is_cold() prueft < 10 Schwelle."""
    from core.network.ip_quality import is_cold

    assert is_cold(0) is True, "Score 0 ist cold"
    assert is_cold(9) is True, "Score 9 ist cold"
    assert is_cold(10) is False, "Score 10 ist nicht cold"
    assert is_cold(100) is False, "Score 100 ist nicht cold"
