"""Test survey/autodoc.py — append-only logging and summary generation.

WARUM: Auto-Dokumentation ist die einzige Quelle für Debugging und Learning.
Append-only JSONL muss atomar schreiben, auch bei Race-Conditions.
Falsche Datei-Pfade oder korrupte JSON-Zeilen zerstören den Lern-Loop.

ARCHITEKTUR: Unittest mit ECHTEN temporären Dateien (tempfile.mkdtemp).
Nicht gemockt — write/read-Zyklus wird tatsächlich ausgeführt,
um Datei-System-Verhalten zu verifizieren.
Kein Chrome, kein WebSocket, kein NIM.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import unittest
import json
import tempfile
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch LOGS_DIR before importing autodoc
import survey.autodoc as ad


class TestLogEarnings(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_logs_completed_survey(self):
        entry = ad.log_earnings(
            survey_id="66768183",
            provider="qualtrics",
            amount=2.50,
            status="completed",
            duration_s=180.5,
        )
        self.assertEqual(entry["survey_id"], "66768183")
        self.assertEqual(entry["amount_eur"], 2.50)
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(entry["provider"], "qualtrics")
        self.assertIn("ts", entry)
        self.assertIn("unix_ts", entry)
        self.assertEqual(entry["type"], "earnings")

    def test_logs_screen_out_zero_amount(self):
        entry = ad.log_earnings(
            survey_id="99999",
            provider="tolunastart",
            amount=0.0,
            status="screen_out",
            duration_s=60.0,
        )
        self.assertEqual(entry["amount_eur"], 0.0)
        self.assertEqual(entry["status"], "screen_out")

    def test_logs_error_zero_amount(self):
        entry = ad.log_earnings(
            survey_id="88888",
            provider="cpx",
            amount=0.0,
            status="error",
            duration_s=5.0,
        )
        self.assertEqual(entry["amount_eur"], 0.0)
        self.assertEqual(entry["status"], "error")

    def test_persists_to_file(self):
        ad.log_earnings("sid1", "qualtrics", 1.00, "completed", 100.0)
        ad.log_earnings("sid2", "tolunastart", 0.50, "completed", 120.0)
        files = list(Path(self.tmp).glob("earnings-*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        e1 = json.loads(lines[0])
        self.assertEqual(e1["survey_id"], "sid1")
        e2 = json.loads(lines[1])
        self.assertEqual(e2["survey_id"], "sid2")

    def test_details_optional(self):
        entry = ad.log_earnings(
            "sid3", "samplicio", 3.00, "completed", 200.0,
            details={"questions_answered": 15}
        )
        self.assertEqual(entry["details"]["questions_answered"], 15)

    def test_daily_file_named_correctly(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        ad.log_earnings("sid", "qualtrics", 1.0, "completed", 60.0)
        fp = Path(self.tmp) / f"earnings-{date_str}.jsonl"
        self.assertTrue(fp.exists())


class TestLogDecision(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_logs_decision(self):
        actions = [
            {"ref": "@e0", "action": "select"},
            {"ref": "@e1", "action": "submit"},
        ]
        ad.log_decision(
            snapshot_elements=8,
            actions=actions,
            nim_calls=1,
            elapsed_ms=120.5,
            survey_id="12345",
            provider="qualtrics",
        )
        fp = list(Path(self.tmp).glob("decisions-*.jsonl"))[0]
        lines = fp.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        self.assertEqual(entry["snapshot_elements"], 8)
        self.assertEqual(entry["actions_count"], 2)
        self.assertEqual(entry["nim_calls"], 1)
        self.assertEqual(entry["elapsed_ms"], 120.5)
        self.assertEqual(entry["survey_id"], "12345")
        self.assertEqual(entry["provider"], "qualtrics")
        self.assertEqual(entry["type"], "decision")

    def test_truncates_actions_to_10(self):
        actions = [{"ref": f"@e{i}", "action": "click"} for i in range(15)]
        ad.log_decision(5, actions, 1, 50.0)
        fp = list(Path(self.tmp).glob("decisions-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(len(entry["actions"]), 10)

    def test_optional_args_can_be_empty(self):
        ad.log_decision(3, [{"ref": "@e0", "action": "click"}], 1, 30.0)
        fp = list(Path(self.tmp).glob("decisions-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["survey_id"], "")
        self.assertEqual(entry["provider"], "")


class TestLogError(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_logs_error(self):
        ad.log_error(
            context="run_survey",
            error="No survey available",
            survey_id="12345",
            provider="qualtrics",
        )
        fp = list(Path(self.tmp).glob("errors-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["context"], "run_survey")
        self.assertEqual(entry["error"], "No survey available")
        self.assertEqual(entry["survey_id"], "12345")
        self.assertEqual(entry["type"], "error")
        self.assertIn("traceback", entry)

    def test_truncates_error_to_500_chars(self):
        long_error = "x" * 1000
        ad.log_error("test", long_error)
        fp = list(Path(self.tmp).glob("errors-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(len(entry["error"]), 500)

    def test_details_optional(self):
        ad.log_error("test", "error", details={"ws_url": "ws://localhost:9999"})
        fp = list(Path(self.tmp).glob("errors-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["details"]["ws_url"], "ws://localhost:9999")


class TestLogSession(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_logs_session_start(self):
        ad.log_session(action="scan", status="running", details={"surveys_available": 3})
        fp = list(Path(self.tmp).glob("sessions-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["action"], "scan")
        self.assertEqual(entry["status"], "running")
        self.assertEqual(entry["type"], "session")
        self.assertEqual(entry["details"]["surveys_available"], 3)

    def test_logs_session_ok(self):
        ad.log_session(action="run", status="ok", details={"completed": 1, "earned": 2.50})
        fp = list(Path(self.tmp).glob("sessions-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["status"], "ok")

    def test_logs_session_error(self):
        ad.log_session(action="login", status="error")
        fp = list(Path(self.tmp).glob("sessions-*.jsonl"))[0]
        entry = json.loads(fp.read_text().strip().split("\n")[0])
        self.assertEqual(entry["status"], "error")


class TestGenerateSummary(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def _write_earnings(self, date_str, entries):
        fp = Path(self.tmp) / f"earnings-{date_str}.jsonl"
        with open(fp, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def _write_errors(self, date_str, count):
        fp = Path(self.tmp) / f"errors-{date_str}.jsonl"
        with open(fp, "w") as f:
            for _ in range(count):
                f.write(json.dumps({"type": "error", "context": "test"}) + "\n")

    def test_empty_logs(self):
        summary = ad.generate_summary(days=1)
        self.assertEqual(summary["total_earned"], 0.0)
        self.assertEqual(summary["surveys_completed"], 0)
        self.assertEqual(summary["surveys_failed"], 0)
        self.assertEqual(summary["errors_count"], 0)
        self.assertEqual(summary["by_provider"], {})

    def test_sums_earnings(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        self._write_earnings(date_str, [
            {"amount_eur": 1.50, "status": "completed", "provider": "qualtrics"},
            {"amount_eur": 2.00, "status": "completed", "provider": "qualtrics"},
            {"amount_eur": 0.00, "status": "screen_out", "provider": "tolunastart"},
        ])
        summary = ad.generate_summary(days=1)
        self.assertEqual(summary["total_earned"], 3.50)
        self.assertEqual(summary["surveys_completed"], 2)
        self.assertEqual(summary["surveys_failed"], 1)

    def test_counts_by_provider(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        self._write_earnings(date_str, [
            {"amount_eur": 1.0, "status": "completed", "provider": "qualtrics"},
            {"amount_eur": 1.0, "status": "completed", "provider": "qualtrics"},
            {"amount_eur": 0.5, "status": "completed", "provider": "tolunastart"},
        ])
        summary = ad.generate_summary(days=1)
        self.assertEqual(summary["by_provider"]["qualtrics"], 2)
        self.assertEqual(summary["by_provider"]["tolunastart"], 1)

    def test_counts_errors(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        self._write_errors(date_str, 5)
        summary = ad.generate_summary(days=1)
        self.assertEqual(summary["errors_count"], 5)

    def test_multiple_days(self):
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self._write_earnings(today, [{"amount_eur": 1.0, "status": "completed", "provider": "q"}])
        self._write_earnings(yesterday, [{"amount_eur": 2.0, "status": "completed", "provider": "q"}])
        summary = ad.generate_summary(days=2)
        self.assertEqual(summary["total_earned"], 3.0)

    def test_skips_malformed_lines(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        fp = Path(self.tmp) / f"earnings-{date_str}.jsonl"
        with open(fp, "w") as f:
            f.write(json.dumps({"amount_eur": 1.0, "status": "completed", "provider": "q"}) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps({}) + "\n")
        summary = ad.generate_summary(days=1)
        # Should not crash, should count valid entries
        self.assertIsInstance(summary["total_earned"], float)


class TestPrintSummary(unittest.TestCase):

    def test_prints_formatted_output(self):
        summary = {
            "total_earned": 3.50,
            "surveys_completed": 5,
            "surveys_failed": 2,
            "errors_count": 1,
            "by_provider": {"qualtrics": 3, "tolunastart": 4},
        }
        out = StringIO()
        with redirect_stdout(out):
            ad.print_summary(summary)
        result = out.getvalue()
        self.assertIn("3.50", result)
        self.assertIn("Completed:", result)
        self.assertIn("qualtrics", result)
        self.assertIn("tolunastart", result)


class TestAutodocIntegration(unittest.TestCase):
    """End-to-end: log + regenerate summary from same tmp dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = ad.LOGS_DIR
        ad.LOGS_DIR = Path(self.tmp)

    def tearDown(self):
        ad.LOGS_DIR = self.orig
        shutil.rmtree(self.tmp)

    def test_log_earnings_then_summary(self):
        ad.log_earnings("sid1", "qualtrics", 1.50, "completed", 120.0)
        ad.log_earnings("sid2", "tolunastart", 0.50, "completed", 90.0)
        ad.log_error("test", "some error")
        summary = ad.generate_summary(days=1)
        self.assertEqual(summary["total_earned"], 2.0)
        self.assertEqual(summary["surveys_completed"], 2)
        self.assertEqual(summary["errors_count"], 1)
        self.assertEqual(summary["by_provider"]["qualtrics"], 1)
        self.assertEqual(summary["by_provider"]["tolunastart"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)