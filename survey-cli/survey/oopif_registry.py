"""================================================================================
OOPIF REGISTRY — Out-Of-Process Iframe Session Routing  (issue #93)
================================================================================

ZWECK
-----
Garantiert, dass cross-origin iframes (OOPIFs) im Scan-Result auftauchen,
auch wenn ``--force-renderer-accessibility`` als Chrome-Flag NICHT gesetzt
ist oder Chrome den AX-Tree cross-process nicht propagiert.

OOPIFs laufen in eigenen Renderer-Prozessen. Aus Sicht von CDP haben sie ein
eigenes ``Target`` — und Commands wie ``DOM.getFlattenedDocument`` oder
``Accessibility.getFullAXTree`` müssen explizit an den OOPIF-Target gerichtet
werden, sonst bekommt man nur Top-Frame-Daten. Ohne diese Brücke "verschwinden"
ganze Survey-Provider-Iframes aus dem Scan (z. B. recaptcha-Sub-Frames, Cint-
Partner-Frames, eingebettete Login-Flows).

WIE
---
Wir nutzen ``Target.setAutoAttach(autoAttach=True, waitForDebuggerOnStart=False,
flatten=True)``. Mit ``flatten=True`` werden ALLE Child-Targets über DIESELBE
WebSocket-Connection multiplexed; jedes Event und jeder Command bekommt ein
``sessionId``-Feld zur Adressierung. Vorteil: KEINE zweite WebSocket-Connection,
keine zusätzlichen Reconnect-Pfade.

Schritte beim ``install()``:

  1. ``Target.setAutoAttach({autoAttach:True, waitForDebuggerOnStart:False,
     flatten:True})`` aufrufen.
     → Chrome attached SOFORT alle bereits existierenden Child-Targets und
       feuert für jeden ein ``Target.attachedToTarget`` Event mit ``sessionId``.
     → Ab jetzt: für jeden NEU entstehenden OOPIF ein weiteres Event.

  2. Event-Handler ``cdp.event_handler`` chainen und auf
     ``Target.attachedToTarget`` reagieren:
       - ``targetInfo.type == "iframe"`` → in Registry eintragen
       - ``frame_id`` ist gleich ``target_id`` für OOPIFs (Chrome-Spec)

  3. ``cdp.drain_events()`` aufrufen, damit Events, die direkt nach
     ``setAutoAttach`` feuerten, noch vor dem nächsten Scan-Step verarbeitet
     werden.

Schritte beim Scannen eines OOPIF (in ``cdp_universal.py`` integriert):

  1. Für jeden ``frame_id`` aus ``frame_to_session``:
       - ``DOM.enable``, ``Accessibility.enable`` gegen ``sessionId``
       - ``DOM.getFlattenedDocument(depth=-1, pierce=True)`` gegen ``sessionId``
       - ``Accessibility.getFullAXTree`` gegen ``sessionId``
       - ``DOM.getBoxModel`` pro Element gegen ``sessionId``
  2. Stable-ID-Schema bleibt: ``sha1(frame_id + ":" + backend_node_id)[:16]``.
     Da ``frame_id`` zwischen Top und OOPIF unterscheidet, kollidieren IDs nicht.

KOORDINATEN-WARNUNG
-------------------
``DOM.getBoxModel`` in einer OOPIF-Session liefert Koordinaten RELATIV zum
OOPIF-Viewport, NICHT zum Top-Viewport. Wer auf ein OOPIF-Element klicken
will, muss diese Translation nachholen (Top-Iframe-bbox + lokale Koordinate).
DIESE PR liefert NUR die Scan-Abdeckung — das Aktoren-Routing für OOPIF-Klicks
bleibt eine Folgeiteration (Plan-Datei wird zu diesem Zeitpunkt geschlossen,
die Limitation ist in AGENTS.md unter Coverage Snapshot dokumentiert).

LIFECYCLE
---------
- OOPIFs verschwinden bei Navigation oder ``iframe.remove()``. Wir bekommen
  ``Target.detachedFromTarget`` und entfernen den Eintrag — sonst zeigen
  zukünftige Scans tote sessionIds, was zu CDP-Errors führt.
- Bei Top-Frame-Navigation (``Page.frameNavigated`` für den Top-Frame) werden
  ALLE Child-Targets detached und neu attached. Unser Handler verarbeitet
  das automatisch über die attach/detach-Events.

GOTCHAS
-------
- ``flatten=True`` ist seit Chrome 79 stabil. Wer auf älteren Versionen
  testet (z. B. Headless-Chromium 78-): nicht unsere Zielgruppe.
- ``Target.setAutoAttach`` fängt KEINE Web-Worker oder ServiceWorker (Type
  ist dann ``"worker"`` bzw. ``"service_worker"``). Wir filtern explizit
  auf ``type == "iframe"`` — Workers haben kein DOM und sind irrelevant
  für Survey-Scan-Coverage.
- Manche Sites haben verschachtelte OOPIFs (OOPIF → OOPIF). Mit
  ``flatten=True`` wird AUTOMATISCH auf jeden Sub-Target rekursiv attached
  (Chrome macht das selbst). Wir müssen nichts Spezielles tun.

API
---
::

    from survey.oopif_registry import OopifRegistry

    with CDPConnection(ws_url) as cdp:
        registry = OopifRegistry(cdp)
        registry.install()
        # Nach jedem Scan / vor jedem Use:
        cdp.drain_events()
        for fid in registry.all_oopif_frames():
            sid = registry.session_for_frame(fid)
            # ... scan that frame via sid ...

BANNED
------
- KEIN separater ``websocket-client`` pro OOPIF — wir nutzen flatten=True.
- KEIN ``Target.attachToTarget(flatten=False)`` — würde eine zweite
  Connection erzwingen.
- KEINE Heuristik à la "guess sessionId from frameId" — IMMER über die
  Registry und nur mit Werten aus ``Target.attachedToTarget`` Events.
================================================================================"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cdp_client import CDPConnection, CDPError


@dataclass(frozen=True)
class OopifSession:
    """Snapshot eines bekannten OOPIF.

    Wird von ``OopifRegistry.snapshot()`` zurückgegeben und vom Scanner
    (``cdp_universal._scan_session``) konsumiert. Die Felder spiegeln 1:1
    den ``Target.attachedToTarget``-Payload, normalisiert auf Strings.
    """

    frame_id: str  # == ``targetInfo.targetId`` für OOPIFs in flatten-Mode
    session_id: str  # CDP ``sessionId`` für Multiplexing über DIESELBE WS
    url: str  # Letzte bekannte URL des OOPIF-Targets


class OopifRegistry:
    """Hält die ``frame_id → session_id`` Map für OOPIFs.

    Die Klasse macht NUR zwei Dinge:
      1. ``Target.setAutoAttach(flatten=True)`` einmalig aufrufen.
      2. Auf ``Target.attachedToTarget``/``Target.detachedFromTarget`` Events
         reagieren und die Map pflegen.

    Sie ruft KEIN ``DOM.*`` oder ``Accessibility.*`` selbst auf — das macht
    ``cdp_universal.scan()`` mit den Werten aus dieser Registry.

    Threading: NICHT thread-safe. Im Survey-Pfad ist die Connection per
    Loop-Thread serialisiert, daher kein Problem.
    """

    def __init__(self, cdp: CDPConnection):
        """Bind registry to a connected ``CDPConnection``.

        Args:
            cdp: Bereits verbundener Sync-CDP-Client. Die Connection muss
                ``event_handler``- und ``session_id``-Support haben (siehe
                ``cdp_client.py`` Erweiterungen für #93/#94).
        """
        self.cdp = cdp
        # frame_id ist der KANONISCHE Schlüssel. Für OOPIFs gilt
        # frame_id == target_id (Chrome-Verhalten in flatten-Mode).
        self.frame_to_session: dict[str, str] = {}
        # Umkehr-Map zum schnellen Aufräumen bei detach (sessionId-zentriert).
        self.session_to_frame: dict[str, str] = {}
        # Voller OOPIF-Eintrag (inkl. URL) — wird vom Scanner als
        # ``fallback_frame_url`` benutzt, wenn der AX-Knoten kein frameId
        # mitliefert. Key ist die session_id (am robustesten gegen detach).
        self._sessions: dict[str, OopifSession] = {}
        self._installed: bool = False
        self._prev_handler: Any = None

    # ── Installation ─────────────────────────────────────────────────

    def install(self) -> None:
        """Aktiviert Auto-Attach und chained den Event-Handler.

        Idempotent: zweiter Aufruf ist no-op.
        """
        if self._installed:
            return

        # Schritt 1: Event-Handler-Chain einbauen, BEVOR wir setAutoAttach
        # rufen. Sonst entstehen Events, die wir noch nicht abfangen.
        self._prev_handler = self.cdp.event_handler

        def _chained(method: str, params: dict, session_id: str | None) -> None:
            if method == "Target.attachedToTarget":
                self._on_attached(params)
            elif method == "Target.detachedFromTarget":
                self._on_detached(params)
            if self._prev_handler is not None:
                try:
                    self._prev_handler(method, params, session_id)
                except Exception:
                    # Event-Handler dürfen die Request-Schleife NIE crashen.
                    pass

        self.cdp.event_handler = _chained

        # Schritt 2: setAutoAttach mit flatten=True.
        # retry=False weil:
        #   - bei Erfolg ist keine Wiederholung nötig (idempotent in Chrome)
        #   - bei Fehler (z. B. älteres Chrome) ist Retry sinnlos
        try:
            self.cdp.call(
                "Target.setAutoAttach",
                {
                    "autoAttach": True,
                    "waitForDebuggerOnStart": False,
                    "flatten": True,
                },
                retry=False,
            )
        except CDPError:
            # Chrome zu alt? Flag nicht akzeptiert? In jedem Fall: weiter
            # ohne OOPIF-Coverage. Der Scanner fällt auf den AX-Tree-Pfad
            # zurück (--force-renderer-accessibility), das ist okay.
            pass

        # Schritt 3: Drain Events, die durch setAutoAttach SOFORT für jeden
        # bereits existierenden OOPIF gefeuert wurden. timeout=0.1s ist
        # generös; bei 0 OOPIFs returnt sofort.
        try:
            self.cdp.drain_events(timeout=0.1)
        except Exception:
            pass

        self._installed = True

    # ── Event-Verarbeitung ───────────────────────────────────────────

    def _on_attached(self, params: dict) -> None:
        """Verarbeitet ``Target.attachedToTarget``.

        ``params`` hat die Form::

            {
              "sessionId": "<opaque-string>",
              "targetInfo": {
                "targetId": "<frame-id-for-iframes>",
                "type": "iframe" | "page" | "worker" | ...,
                "url": "...",
                "title": "...",
                "attached": True
              },
              "waitingForDebugger": False
            }

        Wir interessieren uns NUR für iframes.
        """
        info = params.get("targetInfo") or {}
        ttype = str(info.get("type") or "")
        target_id = str(info.get("targetId") or "")
        session_id = str(params.get("sessionId") or "")
        if not session_id or not target_id:
            return
        if ttype != "iframe":
            return
        # In flatten-Mode ist Chrome-spezifisch: target_id == frame_id für
        # OOPIFs. Same-Origin Iframes werden NICHT als separate Targets
        # behandelt — die sind im Top-Target's AX-Tree enthalten und
        # tauchen hier nicht auf (gewollt).
        self.frame_to_session[target_id] = session_id
        self.session_to_frame[session_id] = target_id
        self._sessions[session_id] = OopifSession(
            frame_id=target_id,
            session_id=session_id,
            url=str(info.get("url") or ""),
        )

    def _on_detached(self, params: dict) -> None:
        """Verarbeitet ``Target.detachedFromTarget``.

        ``params``::

            {"sessionId": "...", "targetId": "..."}
        """
        session_id = str(params.get("sessionId") or "")
        if not session_id:
            return
        self._sessions.pop(session_id, None)
        frame_id = self.session_to_frame.pop(session_id, None)
        if frame_id is not None:
            # Nur entfernen, wenn die Session immer noch zu diesem Frame
            # gehört (theoretisches Race: re-attach zwischen detach-Event
            # und unserer Verarbeitung).
            if self.frame_to_session.get(frame_id) == session_id:
                self.frame_to_session.pop(frame_id, None)

    # ── Public Read ──────────────────────────────────────────────────

    def session_for_frame(self, frame_id: str) -> str | None:
        """Liefert die ``sessionId`` für einen OOPIF-frame_id oder ``None``.

        Args:
            frame_id: Chrome ``frameId`` (== ``targetId`` für OOPIFs).

        Returns:
            sessionId (str) wenn der Frame ein bekannter OOPIF ist, sonst
            ``None``. ``None`` ist auch das Signal "Top-Frame oder Same-
            Origin iframe — kein session-Routing nötig".
        """
        return self.frame_to_session.get(frame_id)

    def all_oopif_frames(self) -> list[str]:
        """Liste aller bekannten OOPIF-frame_ids (Stand: jetzt).

        Reihenfolge ist nicht garantiert. Die Liste ist eine flache Kopie —
        Caller dürfen iterieren ohne sich um Mutation während Iteration zu
        sorgen.
        """
        return list(self.frame_to_session.keys())

    def snapshot(self) -> list[OopifSession]:
        """Liefert eine flache Kopie aller bekannten OOPIF-Sessions.

        Genau das, was ``cdp_universal._scan_session`` braucht: Iteration
        über ``(session_id, frame_id, url)``-Tripel. Die Liste ist ein
        Snapshot — Mutationen an der Registry während der Iteration ändern
        sie nicht.
        """
        return list(self._sessions.values())

    # ── Convenience ──────────────────────────────────────────────────

    def enable(self) -> None:
        """Alias für ``install()``. Existiert nur, weil ``CDPConnection``
        sonst das ganze CDP-Domain-Vokabular ``X.enable()`` benutzt — wir
        bleiben konsistent. Wirft die gleichen Garantien wie ``install()``
        (idempotent, swallows CDP-Errors)."""
        self.install()

    # ── Teardown ─────────────────────────────────────────────────────

    def uninstall(self) -> None:
        """Hängt den Event-Handler aus der Chain wieder aus.

        Achtung: ``Target.setAutoAttach(autoAttach=False)`` rufen wir NICHT —
        Chrome erlaubt das pro Connection nur eingeschränkt und es ist okay,
        bis Connection-Close attached zu bleiben (kostet nichts).
        """
        if not self._installed:
            return
        self.cdp.event_handler = self._prev_handler
        self._prev_handler = None
        self._installed = False
