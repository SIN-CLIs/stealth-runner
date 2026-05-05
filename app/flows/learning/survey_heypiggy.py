#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SURVEY_HEYPIGGY — CUA-ONLY Survey Flow für Heypiggy.com
================================================================================
Repo    : /Users/jeremy/dev/stealth-runner/app/flows/learning/survey_heypiggy.py
Stand   : 2026-05-05
Version : 1.0 (LIVE TESTED mit auto_google_login ✅)
Import  : cli/modules/auto_google_login.py (ERSETZT heypiggy_login_box.py!)

================================================================================
SHELL COMMANDS (learning-by-doing dokumentiert):
================================================================================

## Chrome starten + Login:
from cli.modules.auto_google_login import execute as auto_google_login
result = auto_google_login()
→ {"status": "ok", "pid": 71104, "wid": 56640}

## Survey starten (Dashboard → Survey Card klicken):
# Erst: CDP JS document.querySelectorAll('.survey-item') → finde survey-id
# Dann: document.getElementById('survey-ID').click()
# ODER: CUA click [244] "Umfrage starten" (index variiert!)

## Survey beantworten (CUA-ONLY Loop):
# Loop 50x:
#   1. Radio-Buttons: AXRadioButton klicken (radio_hints match)
#   2. Textfelder: AXTextField → set_value (textarea_value)
#   3. Navigation: "Weiter", "Nächste", "Next" AXButton klicken
#   4. Consent: "Zustimmen und fortfahren", "Akzeptieren" AXButton klicken
#   5. Submit: "Submit", "Send" AXButton klicken

## Balance prüfen:
# _tree() → suche "€" oder "guthaben" → re.search(r'(\d+\.?\d*)', line)

================================================================================
PERSONA (HARDCODED — 2026-05-05):
================================================================================

BERLIN — MÄNNLICH — ANGESTELLTER — MEISTER — DEUTSCH

radio_hints = ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"]
checkbox_hints = ["Keine"]
textarea_value = "Ja"

Address: Kurfürstenstraße 124, 10785 Berlin
Haushalt: 2-Personen
Anstellung: Unbefristet

================================================================================
CRITICAL BUGS (BEHOBEN):
================================================================================

BUG 1: Wrong import (heypiggy_login_box.py gelöscht!)
  ❌ Falsch: from cli.modules.heypiggy_login_box import heypiggy_login
  ✅ Richtig: from cli.modules.auto_google_login import execute as auto_google_login

BUG 2: _get_wid() returned nur wid ohne pid
  ❌ Falsch: wid = _get_wid(pid, ["heypiggy"])
  ✅ Richtig: pid, wid = _find_bot_wid(["heypiggy"]) → auto_google_login gibt pid zurück

BUG 3: _find_idx() nutzt falsche roles
  ❌ Falsch: roles = ["AXButton", "AXLink", "AXRadioButton"]
  ✅ Richtig: roles = ["AXButton", "AXLink", "AXRadioButton", "AXCheckBox"]

BUG 4: list_windows format falsch
  ❌ Falsch: windows = d if isinstance(d, list) else []
  ✅ Richtig: windows = d.get("windows", []) if isinstance(d, dict) else []

================================================================================
SURVEY FLOW (15-50 Fragen typisch):
================================================================================

PRE-SURVEY:
  1. auto_google_login() → Dashboard eingeloggt (pid, wid)
  2. Balance lesen → start_balance = _balance(pid, wid)
  3. Survey finden: document.querySelectorAll('.survey-item') oder CUA "Umfrage starten"

CONSENT:
  4. "Zustimmen und fortfahren" / "Akzeptieren" / "Starten" klicken

SURVEY LOOP (max 50 Iterationen):
  5. AX-Tree lesen: _tree(pid, wid)
  
  6. CONSENT-BUTTONS:
     for kw in ["umfrage starten", "zustimmen und fortfahren", "zustimmen", "starten", "akzeptieren"]:
       idx = _find_idx(tree, kw)
       if idx: _click(pid, wid, idx); sleep(3); break
  
  7. FORWARD-BUTTONS:
     if _click(pid, wid, "weiter") or _click(pid, wid, "nächste") or _click(pid, wid, "next"):
       sleep(3); continue
  
  8. SUBMIT-BUTTONS:
     if _click(pid, wid, "submit") or _click(pid, wid, "send"):
       sleep(3); continue
  
  9. RADIO-HINTS:
     for hint in radio_hints:
       idx = _find_idx(tree, hint, ["AXRadioButton"])
       if idx: _click(pid, wid, idx); sleep(1); break
  
  10. CHECKBOX-HINTS:
      for hint in checkbox_hints:
        idx = _find_idx(tree, hint, ["AXCheckBox"])
        if idx: _click(pid, wid, idx); sleep(1); break
  
  11. TEXTAREA:
      ta = _find_field(tree, "")  # leeres placeholder → freies TextField
      if ta: set_value(ta, textarea_value); sleep(1); continue
  
  12. BREAK wenn nichts mehr gefunden

POST-SURVEY:
  13. Balance lesen: end_balance = _balance(pid, wid)
  14. Return: {"status": "ok", "earned": end_balance - start_balance, ...}

================================================================================
SURVEY PROVIDER PATTERNS:
================================================================================

SAMPLICIO.US (rx.samplicio.us/consent/):
  → Consent → My-Take → Disqualifikation oder Complete
  → Cookie-Consent zuerst akzeptieren

CINT (s.cint.com/Survey/Fingerprint/):
  → Fingerprint → Nfield/Kantar → Fragen
  → Multi-Tab Problem: Nur EIN Tab hat Surveys

NFIELD/KANTAR (nfieldeu-interviewing.nfieldmr.com):
  → Welcome → Audio/Video-Fragen
  → Audio via BlackHole + ffmpeg + NVIDIA Omni

================================================================================
"""

import subprocess
import json
import time
import re
import sys
from pathlib import Path

# Projekt-Root in sys.path für relative Imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _launch():
    # Startet Chrome via playstealth mit Heypiggy Dashboard URL
    # Returns: int — PID des gestarteten Chrome-Prozesses oder None
    # WICHTIG: playstealth gibt MEHRERE JSON-Zeilen zurück, nicht eine!
    r = subprocess.run(
        ["playstealth", "launch", "--url", "https://heypiggy.com/?page=dashboard"],
        capture_output=True, text=True, timeout=30
    )
    for line in r.stdout.strip().split("\n"):
        try:
            d = json.loads(line)
            if d.get("pid"):
                return d.get("pid")
        except:
            pass
    return None


def _windows():
    # Ruft list_windows von cua-driver ab
    # Returns: list — windows aus d.get("windows", [])
    # WICHTIG: Antwort ist DICT {"windows": [...]} nicht ARRAY!
    r = subprocess.run(["cua-driver", "call", "list_windows"], capture_output=True, text=True, timeout=10)
    try:
        d = json.loads(r.stdout)
        return d.get("windows", []) if isinstance(d, dict) else []
    except:
        return []


def _find_bot_wid(keywords=None):
    # Findet Window ID von BOT Chrome (heypiggy-bot-* profile)
    # keywords  : list   — Title-Keywords filtern
    # Returns   : tuple  — (pid, wid) oder (None, None)
    # FILTER: height>100 AND is_on_screen AND "chrome" in app_name
    for w in _windows():
        b = w.get("bounds", {})  # NICHT w.get("frame")!
        t = (w.get("title") or "").lower()
        n = (w.get("app_name") or "").lower()
        pid = w.get("pid")
        if b.get("height", 0) < 100:
            continue
        if "chrome" not in n:
            continue
        if keywords:
            if any(k in t for k in keywords):
                return pid, w.get("window_id")
        else:
            return pid, w.get("window_id")
    return None, None


def _cua(pid, wid, method, params=None):
    # Ruft cua-driver call auf mit JSON input
    # pid       : int     — Chrome Process ID
    # wid       : int     — Window ID
    # method    : str     — "get_window_state" | "click" | "set_value"
    # params    : dict    — method-spezifische Parameter
    # Returns   : dict    — geparste JSON Antwort
    p = dict(params or {})
    p["pid"] = pid
    p["window_id"] = wid
    r = subprocess.run(
        ["cua-driver", "call", method],
        input=json.dumps(p), capture_output=True, text=True, timeout=10
    )
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except:
        return {}


def _tree(pid, wid):
    # Liest AX-Tree eines Windows als Liste von Zeilen
    # pid       : int
    # wid       : int
    # Returns   : list    — tree_markdown.split("\n")
    d = _cua(pid, wid, "get_window_state")
    return d.get("tree_markdown", "").split("\n") if isinstance(d, dict) else []


def _find_idx(tree, keyword, roles=None):
    # Findet element_index durch Keyword + Role-Matching im AX-Tree
    # tree      : list    — output von _tree()
    # keyword   : str     — Label-Text (case-insensitive match)
    # roles     : list    — AXRole-Typen
    # Returns   : int     — element_index oder None
    if roles is None:
        roles = ["AXButton", "AXLink", "AXRadioButton", "AXCheckBox"]
    for role in roles:
        for line in tree:
            if keyword.lower() in line.lower() and role in line:
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    return int(m.group(1))
    return None


def _find_field(tree, placeholder):
    # Findet AXTextField durch Placeholder-Match
    # placeholder : str  — Label-Text (case-insensitive)
    # Returns     : int  — element_index oder None
    for line in tree:
        if placeholder.lower() in line.lower() and "AXTextField" in line:
            m = re.search(r'- \[(\d+)\]', line)
            if m:
                return int(m.group(1))
    return None


def _click(pid, wid, keyword, roles=None):
    # Findet Element + klickt es via cua-driver
    # keyword   : str     — Label-Text
    # roles     : list    — AXRole-Typen
    # Returns   : bool    — True wenn click erfolgreich
    idx = _find_idx(_tree(pid, wid), keyword, roles)
    if idx:
        r = _cua(pid, wid, "click", {"element_index": idx})
        return r.get("stdout", "") and " " in r.get("stdout", "")
    return False


def _type(pid, wid, placeholder, value):
    # Findet AXTextField + trägt Text ein
    # placeholder : str  — Label-Text
    # value       : str  — einzutragender Text
    # Returns     : bool — True wenn erfolgreich
    idx = _find_field(_tree(pid, wid), placeholder)
    if idx:
        r = _cua(pid, wid, "set_value", {"element_index": idx, "value": value})
        return r.get("stdout", "") and " " in r.get("stdout", "")
    return False


def _has(tree, keyword):
    # Prüft ob Keyword im AX-Tree vorkommt
    # Returns: bool
    return any(keyword.lower() in l.lower() for l in tree)


def _balance(pid, wid):
    # Liest aktuelles Guthaben aus Dashboard AX-Tree
    # Returns: float — Balance in EUR oder 0.0 wenn nicht gefunden
    for line in _tree(pid, wid):
        if "money" in line.lower() or "€" in line.lower() or "guthaben" in line.lower():
            m = re.search(r'(\d+\.?\d*)', line)
            if m:
                return float(m.group(1))
    return 0.0


def execute(payload=None):
    """
    SURVEY_HEYPIGGY — CUA-ONLY Survey Flow

    Args:
      payload : dict   — optional, für spätere Erweiterung
                       (radio_hints, checkbox_hints, textarea_value)

    Returns:
      {"status": "ok", "earned": X, "start": Y, "end": Z}
      {"status": "error", "reason": "..."}

    ========================================================================
    FLOW (live dokumentiert 2026-05-05):
    ========================================================================

    1. auto_google_login() → Dashboard eingeloggt
       result = {"status": "ok", "pid": 71104, "wid": 56640}
       wenn status != "ok" → return error

    2. Balance lesen: start_balance = _balance(pid, wid)

    3. Survey Loop (max 50 Iterationen):
       Für jede Runde:
         a. AX-Tree lesen
         b. Consent-Buttons klicken (zustimmen, akzeptieren, starten)
         c. Forward-Buttons klicken (weiter, nächste, next)
         d. Submit-Buttons klicken (submit, send)
         e. Radio-Hints klicken (Berlin, männlich, etc.)
         f. Checkbox-Hints klicken (Keine)
         g. Textarea füllen (Ja)
         h. Break wenn nichts mehr gefunden

    4. Balance lesen: end_balance = _balance(pid, wid)

    5. Return Ergebnis mit earned = end_balance - start_balance

    ========================================================================
    """
    # HARDCODED PERSONA (2026-05-05)
    radio_hints = ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"]
    checkbox_hints = ["Keine"]
    textarea_value = "Ja"

    # STEP 1: Login via auto_google_login (CUA-ONLY 6-Step)
    from cli.modules.auto_google_login import execute as auto_google_login
    result = auto_google_login()
    if result.get("status") != "ok":
        return {"status": "error", "reason": result.get("reason", "login_failed")}
    pid = result.get("pid")
    wid = result.get("wid")

    # STEP 2: Start-Balance lesen
    start_balance = _balance(pid, wid)

    # STEP 3: Survey Loop (max 50 Fragen)
    for _ in range(50):
        t = _tree(pid, wid)
        if not t:
            continue

        # Consent-Buttons zuerst (Zustimmen, Akzeptieren, Starten)
        for kw in ["umfrage starten", "zustimmen und fortfahren", "zustimmen", "starten", "akzeptieren"]:
            if _click(pid, wid, kw):
                time.sleep(3)
                break

        # Forward-Buttons (Weiter, Nächste, Next)
        if _click(pid, wid, "weiter") or _click(pid, wid, "nächste") or _click(pid, wid, "next"):
            time.sleep(3)
            continue

        # Submit-Buttons
        if _click(pid, wid, "submit") or _click(pid, wid, "send"):
            time.sleep(3)
            continue

        # Radio-Hints (Persönliche Daten)
        for hint in radio_hints:
            if _click(pid, wid, hint, ["AXRadioButton"]):
                time.sleep(1)
                break

        # Checkbox-Hints (z.B. "Keine" für "Keine Präferenzen")
        for hint in checkbox_hints:
            if _click(pid, wid, hint, ["AXCheckBox"]):
                time.sleep(1)
                break

        # Textarea (offene Fragen)
        ta = _find_field(t, "")
        if ta:
            _cua(pid, wid, "set_value", {"element_index": ta, "value": textarea_value})
            time.sleep(1)
            continue

        # Nichts mehr gefunden → Survey complete
        break

    # STEP 4: End-Balance lesen
    end_balance = _balance(pid, wid)

    # STEP 5: Return Ergebnis
    return {
        "status": "ok",
        "earned": round(end_balance - start_balance, 2),
        "start": start_balance,
        "end": end_balance,
        "pid": pid,
        "wid": wid
    }


# CLI Entry Point
if __name__ == "__main__":
    result = execute()
    print(json.dumps(result, indent=2))
