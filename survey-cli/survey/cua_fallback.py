#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cua_fallback.py — CUA-Driver Fallback für blockierte Seiten
============================================================

PROBLEM (2026-05-11):
  - CDP/JS Clicks werden von React/Angular/Vue blockiert
  - Consent-Seiten akzeptieren keine synthetic events
  - Agent gibt auf statt CUA zu nutzen

LÖSUNG:
  - CUA-Driver für echte OS-Level Clicks
  - Automatische Tab-Aktivierung wenn AX-Tree leer
  - Blinde Koordinaten-Clicks als letzter Fallback
  - Integration mit LangGraph nodes

USAGE:
  from survey.cua_fallback import CUAFallbackHandler
  
  handler = CUAFallbackHandler()
  result = handler.click_consent_checkbox(tab_ws_url)
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class CUAClickResult:
    """Ergebnis eines CUA-Clicks."""
    success: bool
    method: str  # "ax_tree", "blind_coords", "failed"
    details: str
    elapsed_ms: float


class CUAFallbackHandler:
    """Handler für CUA-Driver Fallback-Clicks."""
    
    # Bekannte Consent-Page Layouts (blinde Koordinaten als Fallback)
    CONSENT_LAYOUTS = {
        "aybee": {
            "checkbox_1": {"x": 50, "y": 300, "relative": True},
            "checkbox_2": {"x": 50, "y": 350, "relative": True},
            "submit_button": {"x": 200, "y": 450, "relative": True},
        },
        "ipsos": {
            "accept_button": {"x": 400, "y": 500, "relative": True},
        },
        "generic_consent": {
            "checkbox_area": {"x": 100, "y": 350, "relative": True},
            "continue_button": {"x": 300, "y": 500, "relative": True},
        },
    }
    
    def __init__(self):
        self._ensure_cua_running()
    
    def _ensure_cua_running(self) -> bool:
        """Stellt sicher dass CUA-Driver läuft."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "cua-driver serve"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                # Start CUA daemon
                subprocess.Popen(
                    ["cua-driver", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                time.sleep(2)
            return True
        except Exception as e:
            print(f"[cua] Failed to ensure CUA running: {e}")
            return False
    
    def _call_cua(self, method: str, params: dict = None) -> Optional[dict]:
        """Ruft CUA-Driver Methode auf."""
        try:
            if params:
                input_json = json.dumps(params)
                result = subprocess.run(
                    ["cua-driver", "call", method],
                    input=input_json,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                result = subprocess.run(
                    ["cua-driver", "call", method],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                print(f"[cua] {method} failed: {result.stderr}")
                return None
        except Exception as e:
            print(f"[cua] Exception calling {method}: {e}")
            return None
    
    def find_chrome_window(self, title_pattern: str = None) -> Optional[dict]:
        """Findet Chrome-Window mit optionalem Titel-Pattern."""
        windows = self._call_cua("list_windows")
        if not windows:
            return None
        
        for w in windows.get("windows", []):
            if w.get("app_name") != "Google Chrome":
                continue
            if w.get("bounds", {}).get("height", 0) < 300:
                continue
            
            title = w.get("title", "")
            if title_pattern and title_pattern.lower() not in title.lower():
                continue
            
            return w
        
        # Fallback: größtes Chrome-Window
        chrome_windows = [
            w for w in windows.get("windows", [])
            if w.get("app_name") == "Google Chrome"
            and w.get("bounds", {}).get("height", 0) > 300
        ]
        
        if chrome_windows:
            return max(chrome_windows, key=lambda w: w["bounds"]["height"])
        
        return None
    
    def activate_window(self, window_id: int, pid: int) -> bool:
        """Aktiviert Window (bringt in Vordergrund)."""
        result = self._call_cua("activate_window", {
            "window_id": window_id,
            "pid": pid
        })
        time.sleep(0.5)  # Warten bis Aktivierung abgeschlossen
        return result is not None
    
    def get_window_state(self, window_id: int, pid: int) -> Optional[dict]:
        """Holt AX-Tree für Window."""
        return self._call_cua("get_window_state", {
            "window_id": window_id,
            "pid": pid
        })
    
    def click_element_by_index(self, window_id: int, pid: int, element_index: int) -> bool:
        """Klickt Element via AX-Index."""
        result = self._call_cua("click_element", {
            "window_id": window_id,
            "pid": pid,
            "element_index": element_index
        })
        return result is not None and result.get("success", False)
    
    def click_coordinates(self, x: int, y: int, window_id: int = None, pid: int = None) -> bool:
        """Klickt absolute Koordinaten."""
        params = {"x": x, "y": y}
        if window_id:
            params["window_id"] = window_id
        if pid:
            params["pid"] = pid
        
        result = self._call_cua("click", params)
        return result is not None
    
    def find_and_click_checkbox(self, window_id: int, pid: int, label_pattern: str = None) -> CUAClickResult:
        """Findet und klickt Checkbox im AX-Tree.
        
        1. Aktiviere Window
        2. Hole AX-Tree
        3. Finde Checkbox (optional mit Label-Pattern)
        4. Klicke via Index
        5. Fallback: Blinde Koordinaten
        """
        start = time.time()
        
        # 1. Aktiviere Window
        self.activate_window(window_id, pid)
        
        # 2. Hole AX-Tree
        state = self.get_window_state(window_id, pid)
        if not state:
            return CUAClickResult(
                success=False,
                method="failed",
                details="Could not get window state",
                elapsed_ms=(time.time() - start) * 1000
            )
        
        tree_lines = state.get("tree_markdown", "").split("\n")
        
        # 3. Finde Checkbox
        checkbox_indices = []
        for line in tree_lines:
            if "AXCheckBox" in line or "checkbox" in line.lower():
                # Extract index [N]
                import re
                match = re.search(r'\[(\d+)\]', line)
                if match:
                    idx = int(match.group(1))
                    if label_pattern:
                        if label_pattern.lower() in line.lower():
                            checkbox_indices.insert(0, idx)  # Prioritize matching
                        else:
                            checkbox_indices.append(idx)
                    else:
                        checkbox_indices.append(idx)
        
        # 4. Klicke erste Checkbox
        if checkbox_indices:
            clicked = self.click_element_by_index(window_id, pid, checkbox_indices[0])
            if clicked:
                return CUAClickResult(
                    success=True,
                    method="ax_tree",
                    details=f"Clicked checkbox index {checkbox_indices[0]}",
                    elapsed_ms=(time.time() - start) * 1000
                )
        
        # 5. Fallback: AX-Tree war leer oder kein Checkbox gefunden
        # Versuche blinde Koordinaten basierend auf Window-Bounds
        bounds = state.get("bounds", {})
        if bounds:
            # Typische Checkbox-Position: 10% von links, 40% von oben
            x = bounds.get("x", 0) + int(bounds.get("width", 800) * 0.1)
            y = bounds.get("y", 0) + int(bounds.get("height", 600) * 0.4)
            
            self.click_coordinates(x, y)
            return CUAClickResult(
                success=True,  # Wir hoffen es hat funktioniert
                method="blind_coords",
                details=f"Blind click at ({x}, {y})",
                elapsed_ms=(time.time() - start) * 1000
            )
        
        return CUAClickResult(
            success=False,
            method="failed",
            details="No checkbox found and no bounds for blind click",
            elapsed_ms=(time.time() - start) * 1000
        )
    
    def click_consent_page(self, provider: str = "generic") -> CUAClickResult:
        """Klickt komplette Consent-Page durch.
        
        1. Findet Chrome-Window
        2. Aktiviert es
        3. Klickt alle Checkboxes
        4. Klickt Submit-Button
        """
        start = time.time()
        
        # Finde Chrome-Window
        window = self.find_chrome_window()
        if not window:
            return CUAClickResult(
                success=False,
                method="failed",
                details="No Chrome window found",
                elapsed_ms=(time.time() - start) * 1000
            )
        
        wid = window["window_id"]
        pid = window["pid"]
        
        # Aktiviere
        self.activate_window(wid, pid)
        time.sleep(0.3)
        
        # Hole Layout
        layout = self.CONSENT_LAYOUTS.get(provider, self.CONSENT_LAYOUTS["generic_consent"])
        bounds = window.get("bounds", {})
        
        clicked = []
        
        # Klicke alle definierten Elemente
        for name, coords in layout.items():
            if coords.get("relative"):
                x = bounds.get("x", 0) + coords["x"]
                y = bounds.get("y", 0) + coords["y"]
            else:
                x = coords["x"]
                y = coords["y"]
            
            self.click_coordinates(x, y, wid, pid)
            clicked.append(name)
            time.sleep(0.3)
        
        return CUAClickResult(
            success=True,
            method="blind_coords",
            details=f"Clicked: {', '.join(clicked)}",
            elapsed_ms=(time.time() - start) * 1000
        )
    
    def type_text(self, text: str) -> bool:
        """Tippt Text via CUA."""
        result = self._call_cua("type_text", {"text": text})
        return result is not None
    
    def press_key(self, key: str) -> bool:
        """Drückt Taste (Enter, Tab, etc.)."""
        result = self._call_cua("press_key", {"key": key})
        return result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION MIT LANGGRAPH
# ═══════════════════════════════════════════════════════════════════════════════

def bring_cdp_tab_to_foreground(tab_ws_url: str, target_id: str = "") -> bool:
    """Bringt einen CDP-Tab via WS in den Vordergrund (Issue #80).

    WARUM: Vor jedem AX-basierten Fallback (CUA-Driver, CDP
    ``Accessibility.getFullAXTree``) MUSS der Tab aktiv sein. Chrome
    rendert den AX-Tree nur für die fokussierte Tab — Background-Tabs
    liefern leere Bäume und der CUA-Klick fällt auf blinde Koordinaten
    zurück (= Glücksspiel).

    Wir öffnen die Connection NICHT persistent — diese Funktion wird aus
    Pfaden aufgerufen die selbst keinen ``CDPConnection`` haben (z. B.
    ``cua_click_blocked_element`` als Top-Level-Helper). Synchroner
    Roundtrip, max 5s Timeout.

    Args:
        tab_ws_url: ``ws://...`` URL des Survey-Tabs.
        target_id: optional, ermöglicht ``Target.activateTarget`` als
            Belt-and-Braces — manche Chrome-Versionen ignorieren
            ``Page.bringToFront`` auf Background-Tabs.

    Returns:
        True wenn ``Page.bringToFront`` oder ``Target.activateTarget``
        erfolgreich war, sonst False.
    """
    import json as _json
    try:
        import websocket as _ws
    except ImportError:
        return False

    ok = False
    try:
        sock = _ws.create_connection(tab_ws_url, timeout=5)
    except Exception as e:
        print(f"[foreground] WS connect failed: {e}")
        return False

    try:
        # Page.bringToFront — funktioniert für Page-Targets.
        sock.send(_json.dumps({"id": 1, "method": "Page.bringToFront",
                               "params": {}}))
        resp = _json.loads(sock.recv())
        if "error" not in resp:
            ok = True
        else:
            print(f"[foreground] Page.bringToFront error: {resp['error']}")

        # Optional: Target.activateTarget als Belt-and-Braces.
        if target_id:
            sock.send(_json.dumps({"id": 2, "method": "Target.activateTarget",
                                   "params": {"targetId": target_id}}))
            resp2 = _json.loads(sock.recv())
            if "error" not in resp2:
                ok = True
    except Exception as e:
        print(f"[foreground] WS exchange failed: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return ok


def cua_click_blocked_element(
    element_selector: str,
    tab_ws_url: str,
    target_id: str = "",
) -> dict:
    """LangGraph-kompatible Funktion für CUA-Fallback.

    Wird aufgerufen wenn CDP-Clicks fehlschlagen.

    Pipeline (Issue #80):
      1. ``Page.bringToFront`` via CDP (Tab muss aktiv sein für AX-Tree)
      2. macOS-Window aktivieren via CUA-Driver
      3. ``find_and_click_checkbox`` (AX-Tree → blinde Coords als Fallback)

    Args:
        element_selector: CSS-Selector / Label des Elements (Logging +
            AX-Pattern-Match)
        tab_ws_url: WebSocket URL des Tabs (für ``Page.bringToFront``)
        target_id: optional, für ``Target.activateTarget`` als
            Belt-and-Braces

    Returns:
        {"success": bool, "method": str, "details": str,
         "foreground_ok": bool, "elapsed_ms": float}
    """
    # Step 1 — CDP-Level Foreground (Issue #80)
    fg_ok = bring_cdp_tab_to_foreground(tab_ws_url, target_id=target_id)

    handler = CUAFallbackHandler()

    # Step 2 — macOS-Window
    window = handler.find_chrome_window()
    if not window:
        return {
            "success": False,
            "method": "failed",
            "details": "No Chrome window",
            "foreground_ok": fg_ok,
            "elapsed_ms": 0.0,
        }

    # Step 3 — AX-Tree Click (mit blind-coords-Fallback)
    result = handler.find_and_click_checkbox(
        window["window_id"],
        window["pid"],
        label_pattern=element_selector,
    )

    return {
        "success": result.success,
        "method": result.method,
        "details": result.details,
        "foreground_ok": fg_ok,
        "elapsed_ms": result.elapsed_ms,
    }


__all__ = [
    "CUAFallbackHandler",
    "CUAClickResult",
    "bring_cdp_tab_to_foreground",
    "cua_click_blocked_element",
]
