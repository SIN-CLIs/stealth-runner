#!/usr/bin/env python3
"""Sicherer Klick — NIEMALS Koordinaten raten.
Benutzt AUSSCHLIESSLICH --element-index (Skylight-CLI lost AX-Frame auf).
"""
import json
import subprocess
import sys

PID = int(sys.argv[1])

def primer():
    """Primer auf (-1,-1) — Chromium User-Activation-Gate."""
    subprocess.run(
        ["skylight-cli", "click", "--pid", str(PID), "--x", "-1", "--y", "-1"],
        capture_output=True, timeout=5
    )

def element_table():
    """Holt alle Elemente (SoM + include-tree)."""
    r = subprocess.run(
        ["skylight-cli", "screenshot", "--pid", str(PID), "--mode", "som", "--include-tree"],
        capture_output=True, text=True, timeout=15
    )
    return json.loads(r.stdout).get("elements", [])

def find_web_button(elements):
    """Erster Web-Button mit AXWebArea im Pfad."""
    for e in elements:
        path = e.get("path", "")
        role = e.get("role", "")
        if "AXWebArea" in path and role in ("AXButton", "AXLink", "AXCheckBox", "AXRadioButton"):
            return e
    return None

def find_any_web_element(elements):
    """Erstes Web-Element (egal welche Rolle), AXWebArea im Pfad."""
    for e in elements:
        if "AXWebArea" in (e.get("path") or ""):
            return e
    # Fallback: erstes Element ab Index 30 (ungefahr Web-Content)
    for e in elements:
        if e.get("index", 0) >= 30:
            return e
    return None

# ── HAUPTPROGRAMM ──
primer()
elements = element_table()

target = find_web_button(elements) or find_any_web_element(elements)

if target is None:
    print("❌ Kein klickbares Element gefunden.")
    sys.exit(1)

print(f"👉 Element [{target['index']}]: {target.get('label','')[:60]}")
print(f"   Frame: x={target['frame']['x']:.0f} y={target['frame']['y']:.0f} "
      f"w={target['frame']['width']:.0f} h={target['frame']['height']:.0f}")

result = subprocess.run(
    ["skylight-cli", "click", "--pid", str(PID), "--element-index", str(target["index"])],
    capture_output=True, text=True, timeout=10
)
out = json.loads(result.stdout)
print(f"✅ Status: {out.get('status')}, point: {out.get('point')}")
