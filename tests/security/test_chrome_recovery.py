"""Tests für Chrome Recovery."""
import pytest
from runner.security import is_chrome_running, relaunch_chrome


def test_chrome_health_check():
    # Starte Chrome manuell
    pid = relaunch_chrome("https://example.com")
    # Haupt-PID wird zurückgegeben, auch wenn psutil sie nicht sofort findet
    assert pid is not None
    logger.info(f"Chrome gestartet mit PID {pid}")

    # Simuliere Crash (nur wenn PID existiert)
    if pid:
        import os
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass  # Prozess schon weg
        # Warte kurz
        import time
        time.sleep(2)
        # Health-Check sollte Recovery auslösen
        state = {"pid": pid, "url": "https://example.com"}
        from runner.security import chrome_health_check
        result = chrome_health_check(state)
        assert result["status"] == "recovered"
        assert result["pid"] != pid  # Neue PID
        logger.info(f"Recovery erfolgreich! Neue PID: {result['pid']}")
