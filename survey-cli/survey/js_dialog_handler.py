"""================================================================================
JS DIALOG HANDLER — auto-dismiss alert/confirm/prompt/beforeunload  (issue #94)
================================================================================

ZWECK
-----
Verhindert, dass die Survey-Pipeline blockiert, sobald eine Webseite einen
nativen JS-Dialog öffnet (``window.alert``, ``window.confirm``,
``window.prompt``, ``beforeunload``). Solche Dialoge halten den Render-Thread
in Chrome an, bis der User klickt — ohne Handler bleibt der Agent für immer
hängen.

Ohne diesen Handler:
  - ``confirm("Wirklich abmelden?")`` mitten im Survey → Agent friert ein
  - ``beforeunload`` bei Submit → Navigation wird blockiert, kein DOM-Change
  - ``alert("Pflichtfeld!")`` → no_dom_change, Agent retried sinnlos

POLICY (AUTO-DISMISS)
---------------------
Die Default-Policy akzeptiert ALLE Dialoge automatisch:

  | Dialogtyp      | Aktion                | Begründung                                |
  |----------------|-----------------------|-------------------------------------------|
  | ``alert``      | accept                | Reines Info-Popup, hat nur "OK"           |
  | ``confirm``    | accept (= "OK")       | Survey-Confirms sind fast immer Bestätig- |
  |                |                       | ungen wie "Antwort absenden?" — Ablehnen  |
  |                |                       | würde den Flow stoppen                    |
  | ``prompt``     | accept mit ``""``     | Free-Form-Text-Eingabe ist hier nicht     |
  |                | + WARNING-Log         | sinnvoll automatisierbar; leerer Wert ist |
  |                |                       | das sicherste Default                     |
  | ``beforeunload``| accept               | Agent-initiierte Navigation soll laufen   |

Wer die Policy ändern will (z. B. ``confirm("Wirklich löschen?")`` → False),
übergibt eine eigene ``DialogPolicy``-Callable an ``JsDialogHandler(policy=...)``.

ZWEI-SCHICHT-VERTEIDIGUNG
-------------------------
Wir können uns NICHT allein auf das CDP-Event verlassen — unser
synchroner ``CDPConnection`` empfängt Events nur als Beifang einer laufenden
``call()``-Antwort (siehe ``cdp_client.py::_recv_until_id``). Wenn zwischen
zwei CDP-Calls eine Sekunde liegt und in dieser Sekunde feuert ``alert()``,
hat Chrome den Render-Thread bereits blockiert, BEVOR wir das Event sehen.
Plus: zwischen Browser-Start und dem ersten ``Page.enable`` ist das Event-
Routing noch nicht aktiv.

Darum kombinieren wir:

  1. **JS-Override (BELT — primary)**
     Via ``Page.addScriptToEvaluateOnNewDocument`` wird ein Skript NEW-
     DOCUMENT-pre-injected, das ``window.alert/confirm/prompt`` durch
     no-op Funktionen ersetzt und ``beforeunload`` neutralisiert.
     → Dialoge entstehen nie. Render-Thread blockiert nie.
     → Funktioniert auch nach Navigation (das Skript läuft bei JEDEM neuen
       Document, vor allen Page-Skripten).

  2. **CDP-Event-Subscribe (BRACES — fallback)**
     Über ``cdp.event_handler``-Chain (siehe ``cdp_client.py::CDPConnection``)
     reagieren wir auf ``Page.javascriptDialogOpening``, falls ein
     Skript-Kontext den Override umgeht (z. B. ``eval``, original-bound
     Referenzen, Iframe-Skripte ohne Override).
     → Dispatch ``Page.handleJavaScriptDialog`` sofort mit accept=True.

Beide Layer arbeiten unabhängig. Wer beide deaktiviert, der will sich
selbst eskalieren.

OOPIF (Out-Of-Process Iframe) — KNOWN LIMITATION
------------------------------------------------
``Page.addScriptToEvaluateOnNewDocument`` und ``Page.javascriptDialogOpening``
gelten pro Target. Dialoge aus OOPIFs (cross-origin iframes) werden vom
Top-Frame-Handler NICHT erfasst.
→ Lösung: Wenn ``OopifRegistry`` (#93) installiert ist, MUSS pro OOPIF-Session
  ein eigener ``JsDialogHandler`` an die jeweilige sessionId gebunden werden.
  Diese Verdrahtung kommt in einer Folgeiteration; bis dahin sind OOPIF-
  Dialoge unhandled (Same-Origin iframes laufen im Top-Target und sind okay).

API
---
::

    from survey.js_dialog_handler import JsDialogHandler

    with CDPConnection(ws_url) as cdp:
        handler = JsDialogHandler(cdp)
        handler.install()
        # ... actuator actions ...
        cdp.drain_events()       # gibt event-handler-Chain Zeit zu laufen
        dialogs = handler.drain()  # → list[dict] aller seit drain() gesehenen Dialoge

OBSERVABILITY
-------------
Jeder gesehene Dialog wird strukturiert protokolliert:

::

    DialogEvent(
        type          = "confirm",
        message       = "Antwort wirklich absenden?",
        default_prompt= "",
        url           = "https://example.com/survey/page5",
        accepted      = True,
        prompt_text   = "",
        ts            = 1715520000.123,
    )

Diese Events können in ``ActionResult.dialogs`` durchgereicht werden
(siehe ``cdp_actuator.py``), sodass Analytics-Aufrufer wissen, dass der
Agent gerade einen Dialog wegzauberte. Wichtig für #83-Observability.

BANNED (siehe AGENTS.md A9 / R10)
---------------------------------
- KEIN ``time.sleep(>3s)`` nach Dialog-Detect — Render-Thread ist nach
  ``handleJavaScriptDialog`` direkt wieder frei.
- KEIN globaler ``window.alert = null`` ohne ``try/catch`` — manche Pages
  re-binden ``alert`` als Property mit getter (würde TypeError werfen).
- KEIN ``Page.handleJavaScriptDialog(accept=False)`` als Default —
  würde den Survey-Flow strukturell stoppen.
================================================================================"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .cdp_client import CDPConnection, CDPError


# ── Datentypen ───────────────────────────────────────────────────────


@dataclass
class DialogEvent:
    """Ein gesehener und behandelter JS-Dialog.

    Felder werden 1:1 in ``ActionResult.dialogs`` als ``dict`` durchgereicht.
    Format ist bewusst stabil — andere Agenten und Analytics verlassen sich
    darauf.
    """

    type: str  # "alert" | "confirm" | "prompt" | "beforeunload"
    message: str  # vom Page-Skript an alert/confirm/prompt gegebener Text
    default_prompt: str  # nur bei type="prompt": defaultPrompt-Parameter
    url: str  # URL des Frames, der den Dialog ausgelöst hat
    accepted: bool  # True = wir haben den Dialog mit "OK" geschlossen
    prompt_text: str  # bei prompt: der Text, den wir injiziert haben (""=leer)
    ts: float  # Wallclock-Zeit (time.time()) der Behandlung


# Policy-Signatur: (dialog_type, message) → (accept, prompt_text)
DialogPolicy = Callable[[str, str], "tuple[bool, str]"]


def default_policy(dialog_type: str, message: str) -> "tuple[bool, str]":
    """Standardrichtlinie: alle Dialoge akzeptieren, prompt → "".

    Begründung pro Fall steht oben im Modul-Docstring (POLICY-Tabelle).
    Wer das ändern will, übergibt seine eigene Policy an ``JsDialogHandler``.

    Args:
        dialog_type: "alert" | "confirm" | "prompt" | "beforeunload"
        message: Text, den die Seite dem User zeigt (kann leer sein).

    Returns:
        (accept, prompt_text)
        - ``accept=True``: Dialog mit "OK" / "Bestätigen" wegklicken.
        - ``prompt_text``: Bei ``prompt`` der Wert, der ins Eingabefeld geht.
                           Default "" (leer) — sicherster Wert für Surveys,
                           die "optionalen" Free-Form-Text abfragen.
    """
    # alle vier Typen → accept; prompt liefert leeren String
    return True, ""


# ── Hauptklasse ──────────────────────────────────────────────────────


class JsDialogHandler:
    """Subscriber für ``Page.javascriptDialogOpening`` + JS-Override.

    Installier den Handler EINMAL pro ``CDPConnection`` (idempotent). Danach
    ist die Connection robust gegen native JS-Dialoge — sie blockieren weder
    den Render-Thread (JS-Override) noch werden sie ignoriert (CDP-Event).

    Threading: NICHT thread-safe. Wenn mehrere Threads dieselbe Connection
    benutzen, externes Locking benutzen. Im Survey-Pfad gibt es nur einen
    Loop-Thread, daher kein Problem.
    """

    # JavaScript, das vor jedem Dokument-Load ausgeführt wird und die
    # nativen Dialog-Funktionen neutralisiert. ``try/catch`` umrandet jede
    # Operation, weil Pages mit strict CSP oder mit Object.defineProperty
    # auf ``alert`` sonst einen TypeError werfen würden, der das ganze
    # Override-Skript abbricht.
    _OVERRIDE_JS = """
    (function() {
      try { window.alert = function(){ return undefined; }; } catch (_) {}
      try { window.confirm = function(){ return true; }; } catch (_) {}
      try { window.prompt = function(){ return ""; }; } catch (_) {}
      try { window.onbeforeunload = null; } catch (_) {}
      try {
        window.addEventListener('beforeunload', function(e){
          try { e.preventDefault(); } catch (_) {}
          try { e.returnValue = ''; } catch (_) {}
          return undefined;
        }, true);
      } catch (_) {}
    })();
    """

    def __init__(
        self,
        cdp: CDPConnection,
        *,
        policy: DialogPolicy | None = None,
    ):
        """Bind handler to a connected ``CDPConnection``.

        Args:
            cdp: Bereits verbundener Sync-CDP-Client.
            policy: Optionale Override-Funktion zur Dialog-Entscheidung.
                Default: ``default_policy`` (alles accepten).
        """
        self.cdp = cdp
        self.policy: DialogPolicy = policy or default_policy
        self.events: list[DialogEvent] = []
        self._installed: bool = False
        self._prev_handler: Any = None

    # ── Installation ─────────────────────────────────────────────────

    def install(self) -> None:
        """Aktiviert beide Schichten (JS-Override + Event-Subscribe).

        Idempotent: zweiter Aufruf ist no-op.
        """
        if self._installed:
            return

        # Schicht 0: Page-Domain aktivieren, damit das Event überhaupt feuert.
        # Ohne ``Page.enable`` liefert CDP keine ``javascriptDialogOpening``-
        # Events. Retry=False, weil der Aufrufer bereits eine verbundene
        # Connection übergeben hat und wir nicht reconnecten wollen.
        try:
            self.cdp.call("Page.enable", retry=False)
        except CDPError:
            # Doppel-Enable ist okay — manche Code-Pfade rufen das schon.
            pass

        # Schicht 1 (BELT): JS-Override vor jedem neuen Dokument-Load.
        # ``Page.addScriptToEvaluateOnNewDocument`` registriert ein Skript,
        # das Chrome auf JEDEM neuen Document automatisch VOR allen Page-
        # Skripten ausführt (genau das, was wir brauchen).
        try:
            self.cdp.call(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": self._OVERRIDE_JS},
                retry=False,
            )
        except CDPError:
            pass

        # Schicht 1b: Aktuelles Document patchen (es war ggf. schon geladen,
        # bevor wir das newDocument-Skript registriert haben).
        try:
            self.cdp.call(
                "Runtime.evaluate",
                {"expression": self._OVERRIDE_JS, "returnByValue": True},
                retry=False,
            )
        except CDPError:
            pass

        # Schicht 2 (BRACES): CDP-Event-Subscribe via event-handler-Chain.
        # Der Sync-Client ruft ``event_handler(method, params, session_id)``
        # für jedes Event auf, das er beim Antwort-Polling sieht. Wir chainen
        # uns VOR einen evtl. existierenden Handler, sodass mehrere Subscriber
        # (z. B. JsDialogHandler + OopifRegistry) parallel laufen können.
        self._prev_handler = self.cdp.event_handler

        def _chained(method: str, params: dict, session_id: str | None) -> None:
            if method == "Page.javascriptDialogOpening":
                # OOPIF-Dialoge haben session_id != None. Wir behandeln nur
                # Top-Frame-Dialoge hier (siehe OOPIF-Limitation oben).
                if session_id is None:
                    self._on_dialog(params)
            # Vorherigen Handler nie unterschlagen.
            if self._prev_handler is not None:
                try:
                    self._prev_handler(method, params, session_id)
                except Exception:
                    # Event-Handler dürfen die Request-Schleife NIE crashen.
                    pass

        self.cdp.event_handler = _chained
        self._installed = True

    # ── Dialog-Verarbeitung ──────────────────────────────────────────

    def _on_dialog(self, params: dict) -> None:
        """Wird vom event-handler-Chain aufgerufen, wenn ein Dialog feuert.

        Ruft die Policy, schickt ``Page.handleJavaScriptDialog`` zurück und
        protokolliert das Event in ``self.events``.

        WICHTIG: Diese Methode darf NIE eine Exception nach außen werfen —
        sie läuft in der Event-Pipeline und ein Crash würde die nächste
        ``call()``-Antwort verschlucken.
        """
        dtype = str(params.get("type") or "alert")
        message = str(params.get("message") or "")
        default_prompt = str(params.get("defaultPrompt") or "")
        url = str(params.get("url") or "")

        try:
            accept, prompt_text = self.policy(dtype, message)
        except Exception:
            # Policy hat selbst geworfen → safest default: accept + leer.
            accept, prompt_text = True, ""

        if dtype == "prompt":
            # Warning-Log: prompt-Dialoge im Survey-Kontext sind ein Hinweis
            # darauf, dass die Seite einen Free-Form-Text-Wert erwartet. Mit
            # leerem Default ist die Survey-Validierung evtl. unzufrieden.
            print(
                f"[js-dialog] WARNING: prompt() dialog seen — accepted with "
                f"prompt_text={prompt_text!r}; msg={message[:80]!r}"
            )

        # Dialog wegklicken. retry=False, weil ein Retry hier sinnlos ist:
        # entweder Chrome hat den Dialog noch offen (Erfolg beim ersten Try)
        # oder er ist schon weg (zweiter Try würde "No dialog is showing"
        # liefern).
        try:
            self.cdp.call(
                "Page.handleJavaScriptDialog",
                {
                    "accept": bool(accept),
                    "promptText": str(prompt_text or ""),
                },
                retry=False,
            )
        except CDPError:
            # Dialog könnte schon vom User / OS / anderen Subscriber
            # geschlossen worden sein — kein Grund zur Panik.
            pass

        self.events.append(
            DialogEvent(
                type=dtype,
                message=message[:500],  # Schutz vor Riesen-Strings
                default_prompt=default_prompt[:500],
                url=url,
                accepted=bool(accept),
                prompt_text=str(prompt_text or "")[:500],
                ts=time.time(),
            )
        )

    # ── Public Read/Reset ────────────────────────────────────────────

    def drain(self) -> list[dict]:
        """Gibt alle seit dem letzten ``drain()`` gesehenen Events zurück
        und leert den internen Puffer.

        Returns:
            Liste von ``DialogEvent``-Dicts (via ``dataclasses.asdict``).
            Leer wenn nichts gesehen wurde.
        """
        events = [asdict(e) for e in self.events]
        self.events = []
        return events

    def peek(self) -> list[DialogEvent]:
        """Wie ``drain()``, aber LÄSST die Events drin. Für Tests / Debug."""
        return list(self.events)

    # ── Teardown ─────────────────────────────────────────────────────

    def uninstall(self) -> None:
        """Hängt den Event-Handler aus der Chain wieder aus.

        Achtung: Der JS-Override (``addScriptToEvaluateOnNewDocument``) bleibt
        an der Connection registriert, bis Chrome den Target neu lädt — Chrome
        bietet keine offizielle API zum Entregistrieren. Das ist okay, weil
        der Override Pages nicht schadet (alle Hooks sind no-ops).
        """
        if not self._installed:
            return
        self.cdp.event_handler = self._prev_handler
        self._prev_handler = None
        self._installed = False
