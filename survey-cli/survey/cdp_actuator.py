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


ISSUE #85: NO_DOM_CHANGE RETRY STRATEGY (Automatischer Klick-Retry)
------
Alte Verhaltensweise: ``actuator.click()`` → bei ``no_dom_change`` Aufgabe.
                       Caller (nodes.py) zählt Failures hoch, triggert
                       CUA-Fallback erst nach 2 globalen Misses.
Problem:
  - Survey steckt fest auf "weicher" Race-Condition (z.B. Submit-Button
    war 100ms disabled durch async validation)
  - CUA-Fallback ist teuer (3-5s extra OS-Level-Klicks) — sollte LAST
    RESORT sein, nicht zweite Wahl
  - Single-Shot-Clicks kollidieren mit Doppelclick-Schutz vieler SPAs

Neue Verhaltensweise: ``actuator.click_with_retry()``
  1. Attempt 1: sofort (delay=0)
  2. Wenn no_dom_change → ``refresh_scan()`` + warten 200ms
  3. Attempt 2: erneut klicken (Element-Cache jetzt frisch!)
  4. Wenn weiter no_dom_change → warten 400ms → Attempt 3
  5. Wenn weiter no_dom_change → warten 800ms → Attempt 4
  6. Nach 4 Fehlversuchen: ActionResult(success=False, attempts=4)
     → Caller darf jetzt CUA-Fallback triggern

WHY EXPONENTIAL BACKOFF?
  - Schnelle SPAs: 1. Attempt klappt meist → 0ms Overhead
  - Mittelschnelle Race-Conditions: 2.-3. Attempt klappt (~600ms Overhead)
  - Echt tote Klicks (Overlay, falscher Selektor): bleiben nach 4 Attempts
    tot → CUA übernimmt
  - Total Worst-Case: ~1.4s extra Wartezeit vor CUA-Eskalation
  - Vermeidet "thundering herd" gegen flackernde Elemente

REFRESH-SCAN ZWISCHEN ATTEMPTS:
  Pflicht. Grund: nach einem fehlgeschlagenen Klick hat das DOM evtl. doch
  minimal verändert (Class-Toggle, hover-state) — das kann den Element-
  Cache invalidieren. Ohne refresh klicken wir auf gestale Koordinaten.


ISSUE #86: ANIMATION WAIT — Position-Stability vor Klick
------
Alte Verhaltensweise: Sofort klicken sobald box-model verfügbar.
Problem:
  - Modal slidet von rechts rein (transform: translateX) — Box ist DA, aber
    pixelt sich noch durch die Viewport. Klick trifft den Pfad, nicht das
    Ziel.
  - Fade-In via opacity hat zwar Position, aber pointer-events sind in
    manchen Frameworks bis Animation-End disabled.
  - Material Ripple, framer-motion, GSAP scale → Center-Pixel verschiebt
    sich um 5-30px während ~150-300ms.
  - Bottom-Sheet/Drawer slidet noch hoch → Hit-Point ist 100px tiefer als
    final, Klick landet auf darunterliegendem Element (Overlay-Backdrop).

Neue Verhaltensweise: ``_wait_for_position_stable(cdp, backend_node_id)``
  1. Polle ``DOM.getBoxModel`` alle 50ms
  2. Vergleiche top-left Koordinaten (content[0], content[1])
  3. Wenn Delta < 2px UND letzte Bewegung > 100ms her → STABIL
  4. Max 1s warten (slidende Modals dauern selten länger)
  5. Return: (stable: bool, wait_ms: float)

INTEGRATION IN click():
  scroll → box → ``_wait_for_position_stable`` → frische box → mouse events

  Wenn die Animation länger als 1s dauert: ActionResult(False, reason=
  "element_still_animating"). click_with_retry (Issue #85) wird dann den
  Klick mit 200ms backoff wiederholen — bis dahin ist die Animation durch.

THRESHOLDS-BEGRÜNDUNG:
  - 2px: kleiner als jeder echte Animation-Frame, aber groß genug um
    Sub-Pixel-Rendering und Anti-Aliasing-Jitter zu absorbieren
  - 100ms quiet: zwei requestAnimationFrame-Zyklen — wenn 6 Frames lang
    keine Bewegung, ist die Animation definitiv durch
  - 1s timeout: 99% aller UI-Animationen sind unter 500ms; 1s lässt auch
    langsame Page-Transitions durch ohne den Survey-Flow zu blockieren


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

    actuator.click(stable_id)                  -> ActionResult   # Single-shot (Low-Level)
    actuator.click_with_retry(stable_id)       -> ActionResult   # Issue #85: Retry-Wrapper (PREFERRED!)
    actuator.fill(stable_id, value)            -> ActionResult
    actuator.press_key(key)                    -> ActionResult   # global key
    actuator.scroll_into_view(stable_id)       -> ActionResult

    ActionResult:
        success:    bool
        reason:     str ("ok" | "navigated"
                          | "no_dom_change" | "no_dom_change_after_retries"
                          | "element_still_animating"             (Issue #86)
                          | "element_still_animating_after_retries" (Issue #86)
                          | "element_not_visible"
                          | "unknown_stable_id"
                          | "scroll_failed: ..." | "dispatch_failed: ...")
        before_hash:    str
        after_hash:     str
        elapsed_ms:     float (GESAMT-Zeit inkl. aller Retries bei click_with_retry)
        new_url:        str   (falls Page.navigate ausgelöst wurde)
        dom_stable_ms:  float (Issue #84: actual MutationObserver wait time)
        attempts:       int   (Issue #85: 1..4 Klick-Versuche)
        position_wait_ms: float (Issue #86: Wartezeit auf Position-Stabilität)

WANN WELCHE METHODE?
--------------------
  - ``click_with_retry()``: STANDARD für alle Button-Klicks aus execute_node.
                             Wickelt Race-Conditions selbst ab (Issue #85).
  - ``click()``:             Low-Level, für internen Gebrauch (z.B. fill()
                             braucht single-shot focus-click) oder Tests.


BANNED (siehe AGENTS.md REGEL 1)
--------------------------------
- KEIN ``el.click()`` via Runtime.evaluate
- KEIN ``el.value = ...``
- KEIN provider-spezifisches JS
- KEINE Action ohne Verify
================================================================================
"""
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .cdp_client import CDPConnection, CDPError
from .cdp_universal import UniversalElement, scan as scan_full
from .js_dialog_handler import JsDialogHandler


# Wartezeit nach mousePressed bevor mouseReleased (in Sekunden).
# 50 ms ist menschlich realistisch (echter Klick ist 40–100 ms).
_MOUSE_HOLD_S = 0.05

# Issue #84: MutationObserver-based DOM Stability
# Statt fixed 300ms, warten wir jetzt auf 500ms DOM-Stille
_DOM_STABILITY_SILENCE_MS = 500  # Keine Mutations für diese Zeit = stabil
_DOM_STABILITY_MAX_WAIT_MS = 5000  # Max 5s warten auf SPA-Rendering

# Tastendrücke pro Sekunde beim Tippen (humanlike).
_KEYS_PER_S = 18.0

# ── Issue #85: no_dom_change Retry Strategy ──────────────────────────
# Wenn ein Klick "no_dom_change" liefert, würde der Survey-Flow stecken
# bleiben. Häufige Ursachen für "no_dom_change":
#   - Element noch nicht final gerendert (Race trotz Issue #84)
#   - Sticky/Fixed Overlay verdeckt den Hit-Point (siehe Issue #86)
#   - Element gerade animiert weg (siehe Issue #87)
#   - Doppelclick-Schutz im SPA-Framework
#   - Async Validation hat den Submit-Button kurzzeitig deaktiviert
#
# Schema (Wartezeit VOR jedem Attempt in ms):
#   Attempt 1: 0      (sofort)
#   Attempt 2: 200    (kurze Pause, evtl. Race-Condition resolved)
#   Attempt 3: 400    (mittlere Pause)
#   Attempt 4: 800    (lange Pause, falls Element ge-throttled)
# Gesamt-Worst-Case: ~1.4s extra Wartezeit auf "echt tote" Klicks.
# Nach 4 fehlgeschlagenen Attempts → zurück an Caller (CUA-Fallback).
_RETRY_MAX_ATTEMPTS = 4
_RETRY_BACKOFF_MS = [0, 200, 400, 800]  # Wartezeit VOR jedem Attempt

# ── Issue #86: Animation Wait (Position-Stability vor Klick) ─────────
# Bevor wir die Maus-Events feuern, prüfen wir dass das Element nicht
# gerade animiert (slidet/faded/scaled). Sonst klicken wir auf eine
# Pixel-Position, an der das Element 50ms später nicht mehr ist.
#
# Algorithmus: Polle Box-Model alle _POLL_INTERVAL_MS, vergleiche
# top-left mit letztem Sample. Wenn Δ < 2px für 100ms am Stück → stabil.
# Max 1s warten — danach gilt das Element als "still_animating" und
# click() returnt entsprechend (click_with_retry retried dann nach 200ms,
# und beim 2. Attempt ist die Animation typischerweise durch).
_POSITION_STABLE_TIMEOUT_S = 1.0  # Max Wartezeit auf Position-Stabilität
_POSITION_STABLE_THRESHOLD_PX = 2.0  # Bewegung unter dieser Distanz = "stabil"
_POSITION_STABLE_QUIET_MS = 100  # Wie lange Δ<threshold sein muss
_POSITION_POLL_INTERVAL_S = 0.05  # 50ms Polling — ~2 Animation-Frames


@dataclass
class ActionResult:
    success: bool
    reason: str = "ok"
    before_hash: str = ""
    after_hash: str = ""
    elapsed_ms: float = 0.0
    new_url: str = ""
    dom_stable_ms: float = 0.0  # Issue #84: MutationObserver wait time
    attempts: int = 1  # Issue #85: Anzahl Klick-Versuche (1 = direkt OK)
    position_wait_ms: float = 0.0  # Issue #86: Wartezeit bis Element-Position stabil
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
        resp = cdp.call_result(
            "Runtime.evaluate",
            {
                "expression": wait_script,
                "awaitPromise": True,
                "timeout": 6000,  # 6s CDP-Timeout (5s script + buffer)
            },
        )
        result = resp.get("result", {}).get("value", {})
        stabilized = result.get("stabilized", False)
        elapsed_ms = result.get("elapsed", int((time.time() - t0) * 1000))
        return stabilized, float(elapsed_ms)
    except CDPError:
        # Bei Error trotzdem kurz warten (fallback)
        time.sleep(0.30)
        elapsed_ms = int((time.time() - t0) * 1000)
        return False, float(elapsed_ms)


def _wait_for_position_stable(
    cdp: CDPConnection,
    backend_node_id: int,
    *,
    timeout_s: float = _POSITION_STABLE_TIMEOUT_S,
    threshold_px: float = _POSITION_STABLE_THRESHOLD_PX,
    quiet_ms: int = _POSITION_STABLE_QUIET_MS,
) -> tuple[bool, float]:
    """Issue #86: Wartet bis das Element nicht mehr animiert.

    Pollt ``DOM.getBoxModel`` alle ~50ms und vergleicht die top-left
    Koordinaten. Sobald die Bewegung zwischen aufeinanderfolgenden Samples
    unter ``threshold_px`` liegt UND das so für mindestens ``quiet_ms``
    bleibt, gilt das Element als stabil.

    WANN IST DAS NÖTIG?
    -------------------
    Bei CSS-Animationen ist das Box-Model SOFORT verfügbar (Browser kennt
    Start- und End-Position), aber die GERENDERTEN Pixel sind irgendwo
    dazwischen. Wer in der Mitte einer Slide-In-Animation klickt, trifft
    das Element entweder nicht oder klickt durch zum Backdrop.

    Typische Szenarien:
      - Modal slidet von rechts ein (transform: translateX 100% → 0%)
      - Toast fadet ein (opacity 0 → 1, oft mit translateY)
      - Material Ripple bei Button-Hover
      - Bottom-Sheet/Drawer (transform: translateY)
      - Tab-Indikator (slider bar zwischen Tabs)
      - framer-motion enter/exit, GSAP timeline, Animate.css

    ALGORITHMUS
    -----------
    ::

        last_pos = None
        last_motion = now
        while elapsed < timeout_s:
            pos = top_left(getBoxModel())
            if last_pos:
                if dist(pos, last_pos) >= threshold_px:
                    last_motion = now          # noch in Bewegung
                elif now - last_motion >= quiet_ms:
                    return (True, elapsed)     # stabil!
            last_pos = pos
            sleep(50ms)
        return (False, elapsed)                # Timeout: still animating

    FAILURE MODES
    -------------
    - Element verschwindet während Animation (display:none → ende):
      getBoxModel wirft → wir loggen und brechen mit (False, elapsed) ab.
      click() returnt dann ``element_not_visible``.
    - Endlose Animation (Ladespinner, Pulse-Indikator): timeout greift,
      Klick wird trotzdem ausgeführt. Vertretbar: wer auf ein dauer-
      animiertes Element klickt, weiß was er tut.
    - Sub-Pixel-Jitter durch GPU-Rendering: 2px Threshold absorbiert das.

    Returns:
        (stable: bool, wait_ms: float)
        - stable=True: Element ist still (oder war von Anfang an still)
        - stable=False: Timeout — Element bewegt sich noch
        - wait_ms: Wie lange wir tatsächlich gewartet haben
    """
    t0 = time.time()
    last_pos: tuple[float, float] | None = None
    last_motion = t0  # Wann zuletzt eine "echte" Bewegung erkannt wurde
    quiet_s = quiet_ms / 1000.0

    while True:
        elapsed = time.time() - t0
        if elapsed >= timeout_s:
            return False, elapsed * 1000.0

        # Position abfragen
        try:
            box = cdp.call_result(
                "DOM.getBoxModel",
                {"backendNodeId": backend_node_id},
            ).get("model")
        except CDPError:
            # Element gerade weg / nicht mehr im DOM → kein stabiler Klick möglich
            return False, (time.time() - t0) * 1000.0

        if not box:
            return False, (time.time() - t0) * 1000.0

        content = box.get("content") or []
        if len(content) < 2:
            return False, (time.time() - t0) * 1000.0

        # top-left als Referenz (content[0]=x_tl, content[1]=y_tl)
        pos = (float(content[0]), float(content[1]))

        if last_pos is not None:
            dx = abs(pos[0] - last_pos[0])
            dy = abs(pos[1] - last_pos[1])
            if dx >= threshold_px or dy >= threshold_px:
                # Echte Bewegung erkannt → Quiet-Timer reset
                last_motion = time.time()
            else:
                # Unter Threshold — prüfen ob lange genug quiet
                if (time.time() - last_motion) >= quiet_s:
                    return True, (time.time() - t0) * 1000.0
        # last_pos initial setzen passiert beim ersten Loop; last_motion bleibt = t0
        last_pos = pos

        time.sleep(_POSITION_POLL_INTERVAL_S)


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
        # ── Issue #94: JS-Dialog-Auto-Dismissal ─────────────────────────
        # Survey-Sites triggern manchmal ``alert()`` / ``confirm()`` (z. B.
        # "Are you sure you want to leave?") oder einen vorgefertigten
        # ``beforeunload``-Prompt. Ohne aktiven Dismiss BLOCKIERT der CDP-
        # Aufruf danach für viele Sekunden bzw. komplett (Chrome wartet auf
        # User-Input). Der Handler subscribet sich in die CDP-Event-Chain
        # und ruft ``Page.handleJavaScriptDialog`` automatisch auf, sobald
        # ``Page.javascriptDialogOpening`` reinkommt.
        #
        # WICHTIG: Vor JEDEM Klick rufen wir ``cdp.drain_events()`` damit
        # nachgereichte Dialog-Events VOR dem nächsten Verify abgearbeitet
        # werden — sonst hängt der DOM-Hash-Vergleich am offenen Dialog.
        self._js_dialog = JsDialogHandler(cdp)
        self._js_dialog.install()

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

    # ── Issue #80: Bring Tab to Foreground ───────────────────────────
    def bring_tab_to_foreground(self) -> bool:
        """Bringt den aktiven CDP-Target (Tab) in den Vordergrund.

        WARUM (Issue #80): Wenn der Survey-Tab nicht im Vordergrund läuft,
        liefert die Accessibility-Tree-Abfrage (sowohl CDP ``Accessibility.
        getFullAXTree`` als auch macOS-AX via CUA) regelmäßig einen LEEREN
        Baum — Chrome rendert AX nur für die aktive Tab. Vor jedem
        AX-basierten Fallback (Consent/Captcha) MUSS daher der Tab via
        ``Page.bringToFront`` aktiviert werden.

        Zusätzlich versuchen wir ``Target.activateTarget`` wenn wir eine
        ``targetId`` aus der CDP-Connection rausziehen können — manche
        Chrome-Versionen ignorieren ``Page.bringToFront`` auf Background-
        Tabs (Chrome-Bug, intermittent).

        Returns:
            True wenn mindestens einer der beiden Calls erfolgreich war.

        Best effort — Fallback-Pfade dürfen NIE den Klick-Pfad brechen,
        daher schluckt der Helper alle ``CDPError``.
        """
        ok = False
        try:
            self.cdp.call("Page.bringToFront", {})
            ok = True
        except CDPError as e:
            # Page.bringToFront ist nur in Page-Targets verfügbar.
            print(f"[foreground] Page.bringToFront failed: {e}")

        # Best-Effort: Wenn wir eine targetId an der Connection finden,
        # rufen wir auch Target.activateTarget. Schaden tut's nicht.
        target_id = getattr(self.cdp, "target_id", "") or ""
        if target_id:
            try:
                self.cdp.call("Target.activateTarget", {"targetId": target_id})
                ok = True
            except CDPError as e:
                print(f"[foreground] Target.activateTarget failed: {e}")
        return ok

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
          scroll → _wait_for_position_stable() (Issue #86) → fresh bbox →
          pre-hash → mouseMove/Press/Release → _wait_for_dom_stable()
          (Issue #84) → post-hash → diff.
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

        # 2) Issue #86: Warten bis Element-Position stabil ist
        # Vor dem Klick prüfen, ob das Element gerade animiert (slidet,
        # faded, scaled). Sonst klicken wir auf eine Position, an der das
        # Element 50ms später nicht mehr ist (→ no_dom_change oder Klick
        # auf Backdrop).
        position_stable, position_wait_ms = _wait_for_position_stable(
            self.cdp,
            el.backend_node_id,
        )
        if not position_stable:
            return ActionResult(
                success=False,
                reason="element_still_animating",
                elapsed_ms=(time.time() - t0) * 1000.0,
                position_wait_ms=position_wait_ms,
            )

        # 3) Frische bbox NACH Stabilität holen (alte bbox aus Scan ist veraltet
        #    UND eine während-der-Animation gemessene Box wäre auch falsch)
        try:
            box = self.cdp.call_result(
                "DOM.getBoxModel", {"backendNodeId": el.backend_node_id}
            ).get("model")
        except CDPError:
            box = None
        if not box:
            return ActionResult(
                False,
                "element_not_visible",
                position_wait_ms=position_wait_ms,
            )

        content = box.get("content") or []
        if len(content) < 8:
            return ActionResult(
                False,
                "element_not_visible",
                position_wait_ms=position_wait_ms,
            )
        xs = content[0::2]
        ys = content[1::2]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0

        # 4) Pre-Hash
        before_hash, before_url = _capture_dom_hash(self.cdp)

        # 5) Maus-Events (mouseMoved erzeugt hover, dann pressed/released)
        try:
            self.cdp.call(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseMoved",
                    "x": cx,
                    "y": cy,
                },
            )
            self.cdp.call(
                "Input.dispatchMouseEvent",
                {
                    "type": "mousePressed",
                    "x": cx,
                    "y": cy,
                    "button": "left",
                    "buttons": 1,
                    "clickCount": 1,
                },
            )
            time.sleep(_MOUSE_HOLD_S)
            self.cdp.call(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseReleased",
                    "x": cx,
                    "y": cy,
                    "button": "left",
                    "buttons": 0,
                    "clickCount": 1,
                },
            )
        except CDPError as e:
            return ActionResult(
                False,
                f"dispatch_failed: {e}",
                position_wait_ms=position_wait_ms,
            )

        # 6a) Issue #94: Pending JS-Dialoge ABRÄUMEN, bevor wir auf DOM-
        # Stabilität warten. Wenn der Klick ``alert()`` / ``confirm()`` /
        # ``beforeunload`` getriggert hat, blockiert sonst der nächste
        # CDP-Call. ``drain_events`` ruft synchron ``self._js_dialog``s
        # Event-Handler auf, der ``Page.handleJavaScriptDialog`` schickt.
        self.cdp.drain_events(timeout=0.1)

        # 6b) Issue #84: Auf SPA-DOM-Stabilität warten (MutationObserver)
        stabilized, dom_stable_ms = _wait_for_dom_stable(self.cdp)

        # 7) Post-Hash + Diff
        after_hash, after_url = _capture_dom_hash(self.cdp)
        elapsed_ms = (time.time() - t0) * 1000.0
        navigated = after_url != before_url
        # Issue #94: Hat unser JS-Dialog-Handler seit Klick-Start (``t0``)
        # mindestens einen Dialog weggeklickt? Wenn ja, gilt der Klick auch
        # ohne sichtbare DOM-Mutation als erfolgreich.
        dialogs_handled = any(ev.ts >= t0 for ev in self._js_dialog.peek())

        if before_hash == after_hash and not navigated and not dialogs_handled:
            return ActionResult(
                success=False,
                reason="no_dom_change",
                before_hash=before_hash,
                after_hash=after_hash,
                elapsed_ms=elapsed_ms,
                dom_stable_ms=dom_stable_ms,
                position_wait_ms=position_wait_ms,
            )

        # Wenn der Klick *nur* einen Dialog ausgelöst und Chrome navigiert hat
        # (beforeunload-Bestätigung), reporten wir das als Erfolg mit reason
        # ``dialog_dismissed`` — der Survey-Solver erkennt dann, dass die
        # Aktion wirken konnte. Issue #94.
        reason = "navigated" if navigated else "ok"
        if dialogs_handled and not navigated and before_hash == after_hash:
            reason = "dialog_dismissed"
        return ActionResult(
            success=True,
            reason=reason,
            before_hash=before_hash,
            after_hash=after_hash,
            elapsed_ms=elapsed_ms,
            new_url=after_url if navigated else "",
            dom_stable_ms=dom_stable_ms,
            position_wait_ms=position_wait_ms,
        )

    def click_with_retry(self, stable_id: str) -> ActionResult:
        """Issue #85: Klick mit automatischem Retry bei ``no_dom_change``.

        Hochlevel-API: Das ist die Methode, die ``execute_node`` aus
        ``graph/nodes.py`` aufruft. Sie wickelt die Retry-Logik komplett
        intern ab, sodass der Caller nur EIN ``ActionResult`` zurückbekommt.

        ALGORITHMUS
        -----------
        ::

            for i in 1..4:
                if i > 1:
                    sleep(_RETRY_BACKOFF_MS[i-1])
                    refresh_scan()             # DOM kann sich minimal geändert haben
                result = self.click(stable_id)
                if result.success:
                    result.attempts = i
                    return result
                if result.reason != "no_dom_change":
                    # Harte Fehler (element_not_visible, dispatch_failed) NICHT retryen
                    result.attempts = i
                    return result
            # Alle 4 Attempts no_dom_change → Caller darf CUA-Fallback fahren
            return ActionResult(success=False, reason="no_dom_change_after_retries",
                                attempts=_RETRY_MAX_ATTEMPTS, ...)

        WICHTIG — WAS WIRD RETRIED, WAS NICHT
        --------------------------------------
        RETRIED:
          - ``no_dom_change``           → Klick hat nichts ausgelöst (Race?)
          - ``element_still_animating`` → Issue #86: Element war noch in
                                          Bewegung. Nach 200ms ist die
                                          Animation meistens durch.
        NICHT RETRIED (sofort zurück):
          - ``unknown_stable_id``   → Element war nie im Cache (refresh_scan
                                      hilft nichts, sid stammt aus altem Scan)
          - ``element_not_visible`` → Scroll oder Box-Model failt
          - ``dispatch_failed``     → CDP-Connection-Problem
          - ``scroll_failed``       → DOM-Operation failt

        REFRESH-SCAN ZWISCHEN ATTEMPTS
        ------------------------------
        Vor Attempt 2/3/4 wird ``refresh_scan()`` gerufen. Das ist
        unverzichtbar, weil:
          1. Box-Koordinaten könnten sich verschoben haben (Layout-Shift)
          2. Element könnte unsichtbar geworden sein (display:none Toggle)
          3. ``stable_id`` ist DOM-strukturell — sollte über minor Mutations
             stabil sein. Wenn nicht mehr im Cache → ``unknown_stable_id``
             und Funktion bricht ab.

        RETURNS
        -------
        ActionResult mit:
          - ``success``: True wenn irgendein Attempt klappte
          - ``attempts``: 1..4 (wie viele Versuche bis Erfolg/Aufgabe)
          - ``reason``:
              * "ok" / "navigated" → erfolgreich
              * "no_dom_change_after_retries" → 4× kein DOM-Change
              * sonstige → harter Abbruch nach Attempt 1
          - ``elapsed_ms``: GESAMT-Zeit über alle Attempts (inkl. Backoffs)
          - Übrige Felder vom LETZTEN Attempt

        BEISPIEL
        --------
        >>> result = actuator.click_with_retry("button_submit_xyz")
        >>> if not result.success and result.reason == "no_dom_change_after_retries":
        ...     # Eskalation: CUA-Fallback (OS-Level-Klick)
        ...     cua_click_blocked_element(...)
        """
        t0 = time.time()
        last_result: ActionResult | None = None

        for attempt_idx in range(_RETRY_MAX_ATTEMPTS):
            attempt_num = attempt_idx + 1

            # Vor Attempts >1: Backoff + Scan refresh
            if attempt_idx > 0:
                backoff_ms = _RETRY_BACKOFF_MS[attempt_idx]
                time.sleep(backoff_ms / 1000.0)
                # Scan refresh: DOM kann sich seit letztem Versuch verändert haben
                # (Layout-Shift, hover-state, async render-completion). Nur so
                # bekommen wir frische Box-Koordinaten.
                try:
                    self.refresh_scan()
                except Exception:
                    # Wenn refresh failed (z.B. tab closed), nutze alten Cache
                    pass

            result = self.click(stable_id)

            # ERFOLG → sofort zurück
            if result.success:
                result.attempts = attempt_num
                result.elapsed_ms = (time.time() - t0) * 1000.0
                return result

            # HARTER FEHLER → nicht retryen (Retry würde nichts ändern)
            # Retryable: no_dom_change (Race) + element_still_animating (Issue #86)
            if result.reason not in ("no_dom_change", "element_still_animating"):
                result.attempts = attempt_num
                result.elapsed_ms = (time.time() - t0) * 1000.0
                return result

            # Weicher Fehler → weiterer Attempt
            last_result = result
            print(
                f"[retry] click {stable_id[:10]} attempt={attempt_num}/{_RETRY_MAX_ATTEMPTS} "
                f"reason={result.reason}, retrying in "
                f"{_RETRY_BACKOFF_MS[min(attempt_idx + 1, _RETRY_MAX_ATTEMPTS - 1)]}ms"
            )

        # Alle Attempts erschöpft (Mix aus no_dom_change und/oder still_animating)
        assert last_result is not None
        # Reason-Wahl: wenn letzter Attempt noch animierte → behalte das Signal,
        # damit Caller weiß warum CUA-Fallback fair ist (Element ist live aber
        # animiert dauerhaft → ggf. Loading-Spinner).
        final_reason = (
            "element_still_animating_after_retries"
            if last_result.reason == "element_still_animating"
            else "no_dom_change_after_retries"
        )
        return ActionResult(
            success=False,
            reason=final_reason,
            before_hash=last_result.before_hash,
            after_hash=last_result.after_hash,
            elapsed_ms=(time.time() - t0) * 1000.0,
            dom_stable_ms=last_result.dom_stable_ms,
            position_wait_ms=last_result.position_wait_ms,
            attempts=_RETRY_MAX_ATTEMPTS,
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
                self.cdp.call(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "modifiers": 4,  # Meta/Ctrl
                        "key": "a",
                        "code": "KeyA",
                    },
                )
                self.cdp.call(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "modifiers": 4,
                        "key": "a",
                        "code": "KeyA",
                    },
                )
                # Delete
                self.cdp.call(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "key": "Delete",
                        "code": "Delete",
                    },
                )
                self.cdp.call(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "key": "Delete",
                        "code": "Delete",
                    },
                )
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
                    self.cdp.call(
                        "Input.dispatchKeyEvent",
                        {
                            "type": "keyDown",
                            "text": ch,
                            "key": ch,
                        },
                    )
                    self.cdp.call(
                        "Input.dispatchKeyEvent",
                        {
                            "type": "keyUp",
                            "key": ch,
                        },
                    )
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
            self.cdp.call(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyDown",
                    "modifiers": modifiers,
                    "key": key,
                    "code": key,
                },
            )
            self.cdp.call(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyUp",
                    "modifiers": modifiers,
                    "key": key,
                    "code": key,
                },
            )
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
