"""================================================================================
UNIVERSAL CDP SCANNER — 100 % Elementabdeckung via Browser-native Primitives
================================================================================

ZWECK
-----
Findet JEDES interaktive Element auf JEDER Webseite — egal ob in Top-Frame,
Cross-Origin-iframe, Same-Origin-iframe, Shadow-DOM (offen oder geschlossen via
``pierce: true``), Angular-CDK-Overlay, Web-Component oder Custom-Element.

Der Scanner ist die kanonische Quelle der Wahrheit. Alle Klick-, Fill-, Verify-
und Captcha-Pfade gehen über die hier vergebenen ``stable_id``-Werte. Wer am
Scanner vorbei DOM manipuliert, lügt sich in die Tasche.


WARUM EIN NEUER SCANNER?
------------------------
Der Vorgänger ``snapshot.py::ELEMENT_EXTRACTOR_JS`` (handgerolltes JavaScript)
ist strukturell kaputt:

  1. ``tag === 'button'`` Switch       → übersieht Custom-Elements und role=button
  2. ``walkShadows(depth > 5)``        → Angular-CDK / LitElement haben 6–8 Levels
  3. Modal-Detection per Viewport-Center → bei Sidebar/Bottom-Sheet falsch
  4. Sort-by-Y als Reihenfolge         → ``flex-direction: row-reverse`` kaputt
  5. iframes werden nur GEZÄHLT, nie betreten → iframe-Content unsichtbar
  6. ``seen.has(el)`` deduped innerhalb EINES Documents → Cross-Frame nutzlos
  7. Provider-spezifische CSS-Klassen hardcoded → jeder neue Provider = Patch

Ergebnis: "Mal findet er alles, mal nichts." Nicht akzeptabel.


WIE ES JETZT FUNKTIONIERT
-------------------------
Statt JavaScript-Heuristik nutzen wir EXAKT die CDP-APIs, die Chrome DevTools
intern für den Inspector verwendet. Diese APIs piercen Shadow-DOM und Frames
ohne manuellen Walker.

Pipeline pro Scan:

  1) ``Page.getFrameTree``
       → Enumeration aller Frames (top + alle iframes inkl. cross-origin)
       → Mapping ``frame_id → url`` zur späteren Captcha-Detection

  2) ``Accessibility.enable`` + ``Accessibility.getFullAXTree``
       → Liefert JEDEN semantisch interaktiven Knoten browserweit:
         role ∈ {button, link, checkbox, radio, textbox, combobox,
                 slider, switch, menuitem, tab, option, treeitem, ...}
       → Inklusive ARIA-überschriebener Rollen auf ``<div>``, ``<span>``
       → Inklusive Custom-Elements (z. B. ``<ps-button role="button">``)
       → Inklusive Web-Components mit shadowRoot
       → ``name``, ``value``, ``description``, ``checked``, ``disabled``,
         ``expanded``, ``selected`` direkt vom Browser geliefert.

  3) ``DOM.getFlattenedDocument(depth=-1, pierce=True)``
       → Kompletter DOM-Baum als flacher Stream
       → Enthält ALLE Frames + ALLE Shadow-Roots (offen & user-agent)
       → ``backendNodeId`` ist STABIL für die Lebenszeit des Documents.

  4) Für jeden AX-Knoten:
       ``Accessibility.getFullAXTree`` liefert ``backendDOMNodeId``.
       Falls fehlt (ignored=true): überspringen.

  5) Box-Model + Sichtbarkeit:
       ``DOM.getBoxModel(backendNodeId)``
       → Pixel-Koordinaten. Fehlt → display:none / detached → bbox=None,
         Element wird trotzdem GELISTET (kann via scrollIntoView sichtbar
         werden), Actuator entscheidet beim Klick.

  6) Stable ID:
       ``sha1(frame_id + ":" + backend_node_id)[:16]``
       → Über mehrere Scans im selben Document stabil
       → Bricht KORREKT, wenn das Document neu lädt (gewollt — neue IDs).


CHROME-FLAGS, DIE GESETZT SEIN MÜSSEN
-------------------------------------
``--force-renderer-accessibility``
    Sonst liefert ``Accessibility.getFullAXTree`` nur den Top-Frame.
    Mit diesem Flag erzwingt Chromium den AX-Tree global inkl. iframes.
    Siehe AGENTS.md REGEL 4 — der Chrome-Startbefehl setzt das bereits.


WAS WIR NICHT TUN
-----------------
- KEIN ``document.querySelectorAll('*')`` Walk → war das alte Modell
- KEINE provider-spezifischen CSS-Klassen
- KEIN Tag-Switch
- KEINE Y-Sort-Reihenfolge (stattdessen DOM-Order, Browser-natürlich)
- KEINE Modal-Detection (Modale sind einfach Elemente mit AX-Rolle)


PUBLIC API
----------
::

    scan(cdp: CDPConnection)             -> ScanResult
    scan_ws(ws_url: str)                 -> ScanResult     # Convenience
    scan_port(port=9999, url_contains="") -> ScanResult     # auto-find tab

    ScanResult.elements: list[UniversalElement]
    UniversalElement:
        stable_id        16-Zeichen-Hex, deterministisch pro Document
        frame_id         CDP frameId (Top-Frame == "")
        backend_node_id  CDP backendNodeId (für DOM.* APIs)
        role             AX-Rolle
        name             AX accessible name (Label)
        value            aktueller Wert
        state            {checked, disabled, expanded, selected, focused,
                          required, readonly}
        bbox             {x, y, width, height} oder None
        tag              HTML-Tag-Name
        attrs            ausgewählte Attribute (id, name, type, ...)
        text             innerText (max 200 Zeichen)
        frame_url        URL des enthaltenden Frames

    ScanResult.captcha_frames: list[{frame_id, url}]
        iframes deren URL nach Captcha aussieht — Routing macht
        ``captcha_router.py``.


BANNED (siehe AGENTS.md REGEL 1 + REGEL 1b)
-------------------------------------------
- KEIN provider-spezifisches CSS-Class-Matching in diesem Modul
- KEINE Y-Sort-Order
- KEIN ``walkShadows`` Re-Implementation
- KEIN Aufruf von ``el.click()`` aus diesem Modul (das macht ``cdp_actuator.py``)
================================================================================
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any

from .cdp_client import CDPConnection, CDPError
from .oopif_registry import OopifRegistry


# AX-Rollen, die als "klickbar/interaktiv" gelten.
# Bewusst großzügig. Lieber zu viel listen als zu wenig.
INTERACTIVE_ROLES: set[str] = {
    "button",
    "link",
    "checkbox",
    "radio",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "tab",
    "treeitem",
    "option",
    "switch",
    "slider",
    "spinbutton",
    "textbox",
    "searchbox",
    "combobox",
    "listbox",
    "scrollbar",
    "progressbar",
    "form",
    "search",
    "group",
    "row",
    "cell",
    "gridcell",
    "columnheader",
    "rowheader",
    "dialog",
    "alertdialog",
    "menu",
    "menubar",
}


@dataclass
class UniversalElement:
    """Ein einzelnes interaktives Element, frame-übergreifend identifizierbar."""

    stable_id: str
    frame_id: str
    backend_node_id: int
    role: str
    name: str = ""
    value: str = ""
    tag: str = ""
    text: str = ""
    state: dict[str, bool] = field(default_factory=dict)
    bbox: dict[str, float] | None = None
    attrs: dict[str, str] = field(default_factory=dict)
    frame_url: str = ""


@dataclass
class ScanResult:
    """Vollständiger Scan eines Browser-Tabs (top frame + alle iframes)."""

    url: str
    title: str
    frame_count: int
    elements: list[UniversalElement] = field(default_factory=list)
    timestamp: str = ""
    captcha_frames: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Captcha-iframe-URL-Patterns (NUR Detection, KEINE Lösung — das macht
# captcha_router.py). Wer hier eintragen will: NUR iframe-URLs, keine
# CSS-Klassen, keine Texte.
_CAPTCHA_URL_HINTS: tuple[str, ...] = (
    "hcaptcha.com",
    "recaptcha",
    "google.com/recaptcha",
    "challenges.cloudflare.com",
    "turnstile",
    "geetest.com",
    "lemin.io",
    "/captcha",
    "/challenge",
    "datadome",
    "perimeterx",
    "px-captcha",
)


def _stable_id(frame_id: str, backend_node_id: int) -> str:
    raw = f"{frame_id}:{backend_node_id}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _node_attr(attrs_array: list[str], key: str) -> str:
    """CDP liefert Attribute als flache Liste [k1, v1, k2, v2, ...]."""
    if not attrs_array:
        return ""
    try:
        return attrs_array[attrs_array.index(key) + 1]
    except (ValueError, IndexError):
        return ""


def _box_to_bbox(box: dict[str, Any] | None) -> dict[str, float] | None:
    """CDP BoxModel ``content`` ist [x1,y1,x2,y2,x3,y3,x4,y4] (4 Eckpunkte)."""
    if not box:
        return None
    content = box.get("content") or []
    if len(content) < 8:
        return None
    xs = content[0::2]
    ys = content[1::2]
    x = min(xs)
    y = min(ys)
    return {
        "x": float(x),
        "y": float(y),
        "width": float(max(xs) - x),
        "height": float(max(ys) - y),
    }


def _ax_property(ax_node: dict[str, Any], key: str) -> Any:
    for p in ax_node.get("properties", []) or []:
        if p.get("name") == key:
            return (p.get("value") or {}).get("value")
    return None


def _ax_string(ax_node: dict[str, Any], key: str) -> str:
    val = (ax_node.get(key) or {}).get("value", "")
    return str(val) if val is not None else ""


def _build_dom_index(
    cdp: CDPConnection,
    *,
    session_id: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Mappt backendNodeId → DOM-Node-Dict via
    ``DOM.getFlattenedDocument(pierce=True)``. Enthält ALLE Frames und
    Shadow-Roots auf der angegebenen Session (None = Top-Target,
    sonst OOPIF-Session aus ``OopifRegistry`` — siehe #93).

    ACHTUNG: ``backendNodeId``-Werte sind nur INNERHALB eines Targets stabil.
    Wer Indizes aus mehreren Sessions mergen will, muss sie via ``frame_id``
    disambiguieren — der ``_stable_id``-Helper macht genau das.
    """
    flat = cdp.call_result(
        "DOM.getFlattenedDocument",
        {"depth": -1, "pierce": True},
        session_id=session_id,
    )
    index: dict[int, dict[str, Any]] = {}
    for n in flat.get("nodes", []):
        bnid = n.get("backendNodeId")
        if bnid:
            index[bnid] = n
    return index


def _build_element(
    ax_node: dict[str, Any],
    dom_node: dict[str, Any] | None,
    bbox: dict[str, float] | None,
    frame_id: str,
    frame_url: str,
) -> UniversalElement | None:
    role = _ax_string(ax_node, "role")
    if not role:
        return None
    backend_node_id = ax_node.get("backendDOMNodeId")
    if not backend_node_id:
        return None

    name = _ax_string(ax_node, "name")
    value = _ax_string(ax_node, "value")
    description = _ax_string(ax_node, "description")
    if not name and description:
        name = description

    state = {
        "checked": bool(_ax_property(ax_node, "checked")),
        "disabled": bool(_ax_property(ax_node, "disabled")),
        "expanded": bool(_ax_property(ax_node, "expanded")),
        "selected": bool(_ax_property(ax_node, "selected")),
        "focused": bool(_ax_property(ax_node, "focused")),
        "required": bool(_ax_property(ax_node, "required")),
        "readonly": bool(_ax_property(ax_node, "readonly")),
    }

    tag = (dom_node or {}).get("nodeName", "").lower()
    attrs_array = (dom_node or {}).get("attributes") or []
    attrs = {
        k: _node_attr(attrs_array, k)
        for k in ("id", "name", "type", "href", "src", "placeholder", "aria-label")
        if _node_attr(attrs_array, k)
    }
    text = (dom_node or {}).get("nodeValue", "") or ""

    return UniversalElement(
        stable_id=_stable_id(frame_id, backend_node_id),
        frame_id=frame_id,
        backend_node_id=int(backend_node_id),
        role=role,
        name=name[:200],
        value=value[:200],
        tag=tag,
        text=text[:200],
        state=state,
        bbox=bbox,
        attrs=attrs,
        frame_url=frame_url,
    )


def _scan_session(
    cdp: CDPConnection,
    *,
    session_id: str | None,
    fallback_frame_id: str,
    fallback_frame_url: str,
    frame_id_to_url: dict[str, str],
    elements_out: list[UniversalElement],
) -> None:
    """Scannt EINE Session (Top oder OOPIF) und appended Elements ``elements_out``.

    Wird sowohl für das Top-Target (``session_id=None``) als auch — seit #93 —
    für jede via ``Target.setAutoAttach(flatten=True)`` attachte OOPIF-Session
    aufgerufen. Die OOPIF-Session hat ihren eigenen Backend-Node-Id-Raum;
    ``_stable_id(frame_id, backend_node_id)`` disambiguiert die IDs zwischen
    Sessions, weil ``frame_id`` als Salt einfließt (siehe REGEL 2).

    Args:
        fallback_frame_id: Für OOPIFs der Frame-Id-String des OOPIF, falls ein
            AX-Knoten kein ``frameId`` mitliefert. Beim Top-Target leer.
        fallback_frame_url: Fallback-URL analog.
    """
    cdp.call("DOM.enable", retry=False, session_id=session_id)
    cdp.call("Accessibility.enable", retry=False, session_id=session_id)

    dom_index = _build_dom_index(cdp, session_id=session_id)
    ax_result = cdp.call_result("Accessibility.getFullAXTree", {}, session_id=session_id)
    ax_nodes = ax_result.get("nodes", [])

    for ax in ax_nodes:
        role = _ax_string(ax, "role")

        # Filter: nur interaktive Rollen ODER nicht-ignored Knoten mit name.
        if role not in INTERACTIVE_ROLES:
            if ax.get("ignored", True):
                continue
            if not _ax_string(ax, "name"):
                continue

        backend_node_id = ax.get("backendDOMNodeId")
        if not backend_node_id:
            continue

        dom_node = dom_index.get(backend_node_id)
        frame_id = ax.get("frameId") or (dom_node or {}).get("frameId") or fallback_frame_id
        frame_url = frame_id_to_url.get(frame_id, fallback_frame_url or "")

        bbox: dict[str, float] | None = None
        try:
            box = cdp.call_result(
                "DOM.getBoxModel",
                {"backendNodeId": backend_node_id},
                session_id=session_id,
            )
            bbox = _box_to_bbox(box.get("model"))
        except CDPError:
            bbox = None  # Element im DOM aber nicht gerendert — wird gelistet.

        el = _build_element(ax, dom_node, bbox, frame_id, frame_url)
        if el is not None:
            elements_out.append(el)


def scan(cdp: CDPConnection) -> ScanResult:
    """Hauptfunktion. Liefert ALLE interaktiven Elemente eines Tabs.

    Voraussetzung: ``cdp`` ist eine bereits verbundene ``CDPConnection`` zum
    Page-Target des zu scannenden Tabs.

    Iframes werden via pierce=True automatisch mitgescannt — kein zusätzlicher
    ``Target.attachToTarget`` nötig für same-process iframes. Cross-origin
    OOPIFs werden seit #93 via ``Target.setAutoAttach(flatten=True)`` als
    eigene Sub-Sessions attached und in einer zweiten Pass-Schleife gescannt
    (siehe ``oopif_registry.py``). Der zusätzliche AX-Tree aus dem Top-Target
    via ``--force-renderer-accessibility`` bleibt als Fallback bestehen für
    Browser-Builds, in denen Flatten-Attach nicht greift.
    """
    cdp.call("DOM.enable", retry=False)
    cdp.call("Page.enable", retry=False)
    cdp.call("Accessibility.enable", retry=False)

    # OOPIF-Auto-Attach AKTIVIEREN bevor wir den AX-Tree pullen, damit die
    # ``Target.attachedToTarget``-Events im Drain-Schritt unten ankommen.
    # Idempotent: mehrfaches ``setAutoAttach`` ist sicher.
    oopif = OopifRegistry(cdp)
    oopif.enable()

    # Metadaten
    meta_resp = cdp.call_result(
        "Runtime.evaluate",
        {"expression": "JSON.stringify({u:location.href,t:document.title})"},
    )
    try:
        meta = json.loads(meta_resp.get("result", {}).get("value", "{}"))
    except json.JSONDecodeError:
        meta = {}

    # frame_id → url Mapping
    frame_tree = cdp.call_result("Page.getFrameTree", {})
    frame_id_to_url: dict[str, str] = {}

    def _walk(node: dict[str, Any]) -> None:
        fr = node.get("frame") or {}
        fid = fr.get("id", "")
        if fid:
            frame_id_to_url[fid] = fr.get("url", "")
        for child in node.get("childFrames", []) or []:
            _walk(child)

    _walk(frame_tree.get("frameTree") or {})

    # Captcha-Frame-Detection (nur URLs sammeln)
    captcha_frames = [
        {"frame_id": fid, "url": furl}
        for fid, furl in frame_id_to_url.items()
        if any(hint in furl.lower() for hint in _CAPTCHA_URL_HINTS)
    ]

    elements: list[UniversalElement] = []

    # Pass 1: Top-Target
    _scan_session(
        cdp,
        session_id=None,
        fallback_frame_id="",
        fallback_frame_url=meta.get("u", ""),
        frame_id_to_url=frame_id_to_url,
        elements_out=elements,
    )

    # Pass 2: Alle OOPIF-Sessions, die Chrome inzwischen attached hat.
    # ``drain_events`` holt nachgereichte ``Target.attachedToTarget``-Events
    # ab, die noch in der WS-Queue liegen (kommen oft erst NACH unseren
    # Top-Target-Calls). Siehe AGENTS.md REGEL 2 für Stable-ID-Salt mit
    # ``frame_id``, damit Backend-Node-Ids zwischen Sessions kollisionsfrei
    # bleiben.
    cdp.drain_events(timeout=0.1)
    for sess in oopif.snapshot():
        try:
            _scan_session(
                cdp,
                session_id=sess.session_id,
                fallback_frame_id=sess.frame_id,
                fallback_frame_url=sess.url,
                frame_id_to_url=frame_id_to_url,
                elements_out=elements,
            )
        except CDPError:
            # OOPIF kann während des Scans navigiert/detached sein. Wir lassen
            # die Session aus und liefern die anderen aus — der Survey-Solver
            # toleriert teilweise fehlende Elemente besser als einen Total-
            # Crash. ``OopifRegistry`` cleant die Session beim nächsten
            # ``detachedFromTarget``-Event auf.
            continue

    return ScanResult(
        url=meta.get("u", ""),
        title=meta.get("t", ""),
        frame_count=len(frame_id_to_url),
        elements=elements,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        captcha_frames=captcha_frames,
    )


def scan_ws(ws_url: str, *, timeout: float = 20.0) -> ScanResult:
    """Convenience: öffnet selbst eine ``CDPConnection``."""
    with CDPConnection(ws_url, timeout=timeout) as cdp:
        return scan(cdp)


def scan_port(port: int = 9999, url_contains: str = "") -> ScanResult:
    """Holt automatisch den aktiven Page-Target und scannt ihn.

    Args:
        port: CDP Debug-Port (Standard 9999 für Jeremy-Profil — AGENTS.md REGEL 4)
        url_contains: Wenn gesetzt → erster Page-Tab dessen URL diesen
            Substring enthält. Sonst erster Page-Tab.
    """
    raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read()
    pages = json.loads(raw)
    chosen = None
    for p in pages:
        if p.get("type") != "page":
            continue
        if url_contains and url_contains not in p.get("url", ""):
            continue
        chosen = p
        break
    if not chosen:
        raise RuntimeError(f"No page tab found on port {port} matching {url_contains!r}")
    return scan_ws(chosen["webSocketDebuggerUrl"])
