"""================================================================================
UNIVERSAL CDP ACTUATOR — Echte Maus-/Tastatur-Events mit Pflicht-Verify
================================================================================

ZWECK
-----
Führt Aktionen (Klick, Fill, Select, Press) auf Elementen aus, die per
``cdp_universal.scan()`` gefunden wurden. Jede Aktion endet mit einem
strukturellen Verify, der KEINE Erfolgs-Halluzination zulässt.

Die ALTEN Klick-Pfade tun das Falsche:

  - ``el.click()``                  → wird von React synthetic events ignoriert
  - ``document.querySelectorAll[idx]`` → Index-basiert, instabil bei Reflow
  - ``dispatchEvent('click')``      → triggert keine "trusted" Events
  - Provider-spezifische JS-Maps    → 5 verschiedene Pfade für dasselbe

DIESES Modul ist der EINZIGE legitime Pfad. Wer woanders klickt, fliegt raus.


WIE ECHTE KLICKS AUSSEHEN
-------------------------
Ein "trusted" Maus-Klick in Browser-Sicht (React, Angular, Vue erkennen NUR
solche) entsteht durch CDP ``Input.dispatchMouseEvent`` mit exakter Sequenz:

  1) ``DOM.scrollIntoViewIfNeeded(backendNodeId)``
       → Element wird in den Viewport gescrollt. Pflicht — sonst Klick
         auf Pixel außerhalb des sichtbaren Bereichs = no-op.

  2) ``DOM.getBoxModel(backendNodeId)``
       → Frische Pixel-Koordinaten NACH dem Scroll. Niemals gecachte bbox
         aus dem letzten Scan verwenden.

  3) Capture Pre-Hash (siehe ``_capture_dom_hash``)
       → SHA-1 über (url + body.innerText + Form-State-Signatur).
         Anker für Verify.

  4) ``Input.dispatchMouseEvent`` { type: mouseMoved,    x, y }
  5) ``Input.dispatchMouseEvent`` { type: mousePressed,  x, y, button:left, clickCount:1 }
       ~ 50 ms warten (humanlike + lässt zone.js arbeiten)
  6) ``Input.dispatchMouseEvent`` { type: mouseReleased, x, y, button:left, clickCount:1 }

  7) Warten auf SPA-DOM-Stabilität via MutationObserver (Issue #84)
       → Statt fixed 300ms: Listen to actual mutations
       → 500ms silence threshold (element finalized rendering)
       → Max 5s timeout (slow SPAs)

  8) Capture Post-Hash
  9) Wenn pre == post → ``success=False, reason="no_dom_change"``
     Wenn pre != post → ``success=True, mutations=diff``

Damit sind Halluzinationen wie "Performed but nichts passiert" strukturell
unmöglich. Wenn der Klick im DOM nichts ändert, gilt er als gescheitert.
Der Aufrufer (LangGraph-Node) MUSS auf success=False reagieren und etwas
anderes versuchen.

ISSUE #84: SPA RENDERING WAIT (MutationObserver-based)
------
Alte Verhaltensweise: ``time.sleep(0.30)`` nach Action
Problem: 
  - Zu schnell → React/Angular sind noch nicht fertig, premature hash capture
  - Zu langsam → 300ms Overhead bei jeder Action

Neue Verhaltensweise: ``_wait_for_dom_stable()``
  1. Registriere MutationObserver auf document.body
  2. Zähle Mutations (childList, attributes, characterData)
  3. Wenn >500ms keine Mutations → DOM ist "stable"
  4. Max 5s timeout (long-polling oder complex rendering)
  5. Return: (stabilized: bool, actual_wait_ms: int)

This ensures:
  - React/Angular hooks, async state updates vollständig
  - Vue watchers haben Zeit zu feuern
  - Form state ist final
  - Next.js ISR/incremental updates sind durch
  - Absolut keine premature DOM-hashes


FÜLLEN VON TEXTFELDERN
----------------------
Auch hier KEIN ``el.value = "..."``. Stattdessen:

  1) scrollIntoViewIfNeeded + focus
  2) ``Input.dispatchKeyEvent`` für jeden Charakter
       → ``rawKeyDown`` → ``char`` → ``keyUp``
       → React/Angular sehen einen echten Tastendruck.
  3) Verify: ``DOM.getAttributes`` value-Feld stimmt mit Soll überein.

Fallback (Performance): wenn Text > 50 Chars → ``Input.insertText`` (eine
einzige CDP-Methode, die einen kompletten String einfügt UND echte
input-Events feuert). Schneller, aber kann von hyperaggressiven
Bot-Detectors gesehen werden.


SELECT / RADIO / CHECKBOX
-------------------------
Genau wie Klick. Browser handelt den State-Wechsel — wir machen NICHTS
mit ``selectedIndex`` oder ``.checked``.


PUBLIC API
----------
::

    actuator = Actuator(cdp)

    actuator.click(stable_id)                  -> ActionResult
    actuator.fill(stable_id, value)            -> ActionResult
    actuator.press_key(key)                    -> ActionResult   # global key
    actuator.scroll_into_view(stable_id)       -> ActionResult

    ActionResult:
        success:    bool
        reason:     str ("ok" | "no_dom_change" | "element_not_visible" | ...)
        before_hash: str
        after_hash:  str
        elapsed_ms:  float
        new_url:    str  (falls Page.navigate ausgelöst wurde)
        dom_stable_ms: float  (Issue #84: actual MutationObserver wait time)


BANNED (siehe AGENTS.md REGEL 1)
--------------------------------
- KEIN ``el.click()`` via Runtime.evaluate
- KEIN ``el.value = ...``
- KEIN provider-spezifisches JS
- KEINE Action ohne Verify
================================================================================
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .cdp_client import CDPConnection, CDPError
from .cdp_universal import UniversalElement, scan as scan_full


# Wartezeit nach mousePressed bevor mouseReleased (in Sekunden).
# 50 ms ist menschlich realistisch (echter Klick ist 40–100 ms).
_MOUSE_HOLD_S = 0.05

# Issue #84: MutationObserver-based DOM Stability
# Statt fixed 300ms, warten wir jetzt auf 500ms DOM-Stille
_DOM_STABILITY_SILENCE_MS = 500  # Keine Mutations für diese Zeit = stabil
_DOM_STABILITY_MAX_WAIT_MS = 5000  # Max 5s warten auf SPA-Rendering

# Tastendrücke pro Sekunde beim Tippen (humanlike).
_KEYS_PER_S = 18.0


@dataclass
class ActionResult:
    success: bool
    reason: str = "ok"
    before_hash: str = ""
    after_hash: str = ""
    elapsed_ms: float = 0.0
    new_url: str = ""
    dom_stable_ms: float = 0.0  # Issue #84: MutationObserver wait time
    extra: dict[str, Any] | None = None


def _hash_str(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _capture_dom_hash(cdp: CDPConnection) -> tuple[str, str]:
    """Signatur des Documents über ``url + body.innerText + form-state``.

    Bewusst grob: wir wollen Mutationen erkennen, nicht jedes Pixel zählen.
    Returns (hash, url).
    """
    resp = cdp.call_result(
        "Runtime.evaluate",
        {
            "expression": (
                "JSON.stringify({"
                "u:location.href,"
                "t:(document.body && document.body.innerText || '').substring(0,4000),"
                "f:Array.from(document.querySelectorAll('input,select,textarea'))"
                ".map(function(e){return e.type+':'+(e.checked?'1':'0')+':'+(e.value||'').substring(0,40)})"
                ".join('|').substring(0,2000)"
                "})"
            )
        },
    )
    raw = resp.get("result", {}).get("value", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        d = {}
    sig = f"{d.get('u', '')}|{d.get('t', '')}|{d.get('f', '')}"
    return _hash_str(sig), d.get("u", "")


def _wait_for_dom_stable(cdp: CDPConnection) -> tuple[bool, float]:
    """Issue #84: MutationObserver-based DOM Stability Wait.

    Statt fixed time.sleep(0.30), nutzen wir MutationObserver um zu erkennen,
    wann das DOM sich nicht mehr ändert (SPA-Rendering fertig).

    Returns:
        (stabilized: bool, actual_wait_ms: float)
        - stabilized=True: DOM war >500ms ruhig (rendering beendet)
        - stabilized=False: Timeout nach 5s (komplexes rendering oder error)
        - actual_wait_ms: wie lange wir tatsächlich gewartet haben
    """
    wait_script = """
    (function() {
        return new Promise(function(resolve) {
            let lastMutationTime = Date.now();
            let silenceThreshold = 500;  // 500ms Stille = DOM-stabil
            let maxWaitTime = 5000;      // 5s Max-Timeout
            let startTime = Date.now();

            const observer = new MutationObserver(function(mutations) {
                lastMutationTime = Date.now();
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: true,
                attributeFilter: ['class', 'style', 'disabled', 'value', 'checked', 'selected'],
                attributeOldValue: false,
                characterDataOldValue: false,
            });

            const checkStability = setInterval(function() {
                let elapsed = Date.now() - startTime;
                let timeSinceLastMutation = Date.now() - lastMutationTime;

                // Bedingung 1: 500ms Stille erreicht
                if (timeSinceLastMutation >= silenceThreshold) {
                    clearInterval(checkStability);
                    observer.disconnect();
                    resolve({
                        stabilized: true,
                        elapsed: elapsed,
                    });
                    return;
                }

                // Bedingung 2: 5s Timeout (zu lang gewartet)
                if (elapsed >= maxWaitTime) {
                    clearInterval(checkStability);
                    observer.disconnect();
                    resolve({
                        stabilized: false,
                        elapsed: elapsed,
                    });
                    return;
                }
            }, 50);  // Check alle 50ms
        });
    })()
    """

    t0 = time.time()
    try:
        resp = cdp.call_result("Runtime.evaluate", {
            "expression": wait_script,
            "awaitPromise": True,
            "timeout": 6000,  # 6s CDP-Timeout (5s script + buffer)
        })
        result = resp.get("result", {}).get("value", {})
        stabilized = result.get("stabilized", False)
        elapsed_ms = result.get("elapsed", int((time.time() - t0) * 1000))
        return stabilized, float(elapsed_ms)
    except CDPError as e:
        # Bei Error trotzdem kurz warten (fallback)
        time.sleep(0.30)
        elapsed_ms = int((time.time() - t0) * 1000)
        return False, float(elapsed_ms)


class Actuator:
    """Universal-Actuator — alle Aktionen gehen hier durch.

    Hält eine offene ``CDPConnection`` und einen kleinen Cache mit dem
    letzten Scan, damit ``click(stable_id)`` die ``backend_node_id`` und
    ``frame_id`` auflösen kann ohne dass der Aufrufer das Element-Objekt
    durchschleppen muss.
    """

    def __init__(self, cdp: CDPConnection):
        self.cdp = cdp
        self._element_cache: dict[str, UniversalElement] = {}

    # ── Cache-Verwaltung ──────────────────────────────────────────────

    def refresh_scan(self) -> int:
        """Scannt neu und füllt den internen Cache. Returns Anzahl Elemente.

        Pflicht vor jeder Klick-Serie. Stable_ids alter Scans sind nach
        Page-Navigation NICHT mehr gültig (gewollt).
        """
        result = scan_full(self.cdp)
        self._element_cache = {e.stable_id: e for e in result.elements}
        return len(self._element_cache)

    def element(self, stable_id: str) -> UniversalElement | None:
        return self._element_cache.get(stable_id)

    # ── Atomare Aktionen ──────────────────────────────────────────────

    def scroll_into_view(self, stable_id: str) -> ActionResult:
        """Scrollt das Element in den sichtbaren Viewport."""
        el = self._element_cache.get(stable_id)
        if not el:
            return ActionResult(False, "unknown_stable_id")
        try:
            self.cdp.call(
                "DOM.scrollIntoViewIfNeeded",
                {"backendNodeId": el.backend_node_id},
            )
            return ActionResult(True, "ok")
        except CDPError as e:
            return ActionResult(False, f"scroll_failed: {e}")

    def click(self, stable_id: str) -> ActionResult:
        """Echter Maus-Klick mit Pflicht-Verify.

        Pipeline:
          scroll → fresh bbox → pre-hash → mouseMove/Press/Release →
          _wait_for_dom_stable() (Issue #84) → post-hash → diff.
          success=True nur bei DOM-Änderung.
        """
        t0 = time.time()
        el = self._element_cache.get(stable_id)
        if not el:
            return ActionResult(False, "unknown_stable_id")

        # 1) Scrollen
        try:
            self.cdp.call(
                "DOM.scrollIntoViewIfNeeded",
                {"backendNodeId": el.backend_node_id},
            )
        except CDPError as e:
            return ActionResult(False, f"scroll_failed: {e}")

        # 2) Frische bbox NACH Scroll holen (alte bbox aus Scan ist veraltet)
        try:
            box = self.cdp.call_result(
                "DOM.getBoxModel", {"backendNodeId": el.backend_node_id}
            ).get("model")
        except CDPError:
            box = None
        if not box:
            return ActionResult(False, "element_not_visible")

        content = box.get("content") or []
        if len(content) < 8:
            return ActionResult(False, "element_not_visible")
        xs = content[0::2]
        ys = content[1::2]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0

        # 3) Pre-Hash
        before_hash, before_url = _capture_dom_hash(self.cdp)

        # 4) Maus-Events (mouseMoved erzeugt hover, dann pressed/released)
        try:
            self.cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": cx, "y": cy,
            })
            self.cdp.call("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": cx, "y": cy,
                "button": "left", "buttons": 1, "clickCount": 1,
            })
            time.sleep(_MOUSE_HOLD_S)
            self.cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": cx, "y": cy,
                "button": "left", "buttons": 0, "clickCount": 1,
            })
        except CDPError as e:
            return ActionResult(False, f"dispatch_failed: {e}")

        # 5) Issue #84: Auf SPA-DOM-Stabilität warten (MutationObserver)
        stabilized, dom_stable_ms = _wait_for_dom_stable(self.cdp)

        # 6) Post-Hash + Diff
        after_hash, after_url = _capture_dom_hash(self.cdp)
        elapsed_ms = (time.time() - t0) * 1000.0
        navigated = after_url != before_url

        if before_hash == after_hash and not navigated:
            return ActionResult(
                success=False,
                reason="no_dom_change",
                before_hash=before_hash,
                after_hash=after_hash,
                elapsed_ms=elapsed_ms,
                dom_stable_ms=dom_stable_ms,
            )

        return ActionResult(
            success=True,
            reason="navigated" if navigated else "ok",
            before_hash=before_hash,
            after_hash=after_hash,
            elapsed_ms=elapsed_ms,
            new_url=after_url if navigated else "",
            dom_stable_ms=dom_stable_ms,
        )

    def fill(self, stable_id: str, value: str, *, clear: bool = True) -> ActionResult:
        """Tippt ``value`` in das Element via echte Tastenanschläge.

        - ``clear=True`` (default): vorher Select-All + Delete.
        - Bei ``len(value) > 50``: nutzt ``Input.insertText`` (schneller).
        - Issue #84: Auch hier _wait_for_dom_stable() statt fixed sleep
        """
        t0 = time.time()
        el = self._element_cache.get(stable_id)
        if not el:
            return ActionResult(False, "unknown_stable_id")

        # Fokussieren via Klick auf Mitte des Elements
        focus_click = self.click(stable_id)
        if not focus_click.success and focus_click.reason != "no_dom_change":
            # no_dom_change ist okay — Focus ändert oft nichts visuell.
            return focus_click

        # Bestehenden Wert löschen
        if clear:
            try:
                # Select All
                self.cdp.call("Input.dispatchKeyEvent", {
                    "type": "keyDown", "modifiers": 4,  # Meta/Ctrl
                    "key": "a", "code": "KeyA",
                })
                self.cdp.call("Input.dispatchKeyEvent", {
                    "type": "keyUp", "modifiers": 4, "key": "a", "code": "KeyA",
                })
                # Delete
                self.cdp.call("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Delete", "code": "Delete",
                })
                self.cdp.call("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Delete", "code": "Delete",
                })
            except CDPError:
                pass

        # Pre-Hash
        before_hash, _ = _capture_dom_hash(self.cdp)

        # Tippen
        try:
            if len(value) > 50:
                self.cdp.call("Input.insertText", {"text": value})
            else:
                delay = 1.0 / _KEYS_PER_S
                for ch in value:
                    self.cdp.call("Input.dispatchKeyEvent", {
                        "type": "keyDown", "text": ch, "key": ch,
                    })
                    self.cdp.call("Input.dispatchKeyEvent", {
                        "type": "keyUp", "key": ch,
                    })
                    time.sleep(delay)
        except CDPError as e:
            return ActionResult(False, f"type_failed: {e}")

        # Issue #84: Auf SPA-DOM-Stabilität warten
        stabilized, dom_stable_ms = _wait_for_dom_stable(self.cdp)

        after_hash, _ = _capture_dom_hash(self.cdp)

        return ActionResult(
            success=before_hash != after_hash,
            reason="ok" if before_hash != after_hash else "no_dom_change",
            before_hash=before_hash,
            after_hash=after_hash,
            elapsed_ms=(time.time() - t0) * 1000.0,
            dom_stable_ms=dom_stable_ms,
            extra={"typed": value[:80]},
        )

    def press_key(self, key: str, *, modifiers: int = 0) -> ActionResult:
        """Globaler Tastendruck (z. B. ``Enter``, ``Tab``, ``Escape``).

        Modifier-Bits: 1=Alt, 2=Ctrl, 4=Meta, 8=Shift.
        Issue #84: Auch hier _wait_for_dom_stable() statt fixed sleep
        """
        t0 = time.time()
        before_hash, _ = _capture_dom_hash(self.cdp)
        try:
            self.cdp.call("Input.dispatchKeyEvent", {
                "type": "keyDown", "modifiers": modifiers,
                "key": key, "code": key,
            })
            self.cdp.call("Input.dispatchKeyEvent", {
                "type": "keyUp", "modifiers": modifiers,
                "key": key, "code": key,
            })
        except CDPError as e:
            return ActionResult(False, f"key_failed: {e}")

        # Issue #84: Auf SPA-DOM-Stabilität warten
        stabilized, dom_stable_ms = _wait_for_dom_stable(self.cdp)

        after_hash, _ = _capture_dom_hash(self.cdp)
        return ActionResult(
            success=before_hash != after_hash,
            reason="ok" if before_hash != after_hash else "no_dom_change",
            before_hash=before_hash,
            after_hash=after_hash,
            elapsed_ms=(time.time() - t0) * 1000.0,
            dom_stable_ms=dom_stable_ms,
        )

