"""================================================================================
survey/auth/login_verifier.py — HeyPiggy Login State Detector via CUA/AX-Tree
================================================================================

ZWECK:
  Prüft OB der HeyPiggy Dashboard bereits eingeloggt ist.
  Verwendet CUA (macOS Accessibility API) um "abmelden" Button im AX-Tree
  zu suchen. Wenn "abmelden" sichtbar → User ist eingeloggt.

WARUM nicht einfach URL prüfen?
  → Dashboard-URL ist gleich egal ob eingeloggt oder nicht:
    https://www.heypiggy.com/?page=dashboard
  → Unterschied ist im DOM: Eingeloggt = Header zeigt "abmelden".
  → Ausgeloggt = Header zeigt "anmelden" / Google Login Button.
  → CDP/Playwright könnte prüfen, ABER:
    - Shadow-DOM blockiert manche Elemente.
    - Cookies könnten fehlen → Seite zeigt Login-Maske.
  → CUA/AX sieht die Elemente unabhängig vom DOM/Shadow-DOM.

WARUM "abmelden" als Indicator?
  → "abmelden" erscheint NUR wenn eingeloggt (in Dashboard-Header).
  → "anmelden" erscheint wenn ausgeloggt.
  → "abmelden" ist ein starker (strong) Indicator → zuverlässig.
  → False-Positives unwahrscheinlich: Keine Survey fragt nach "abmelden".

WARUM AX-Tree (nicht DOM)?
  → DOM: JavaScript kann Elemente verstecken/ändern (Anti-Bot).
  → AX-Tree: Accessibility Tree ist für Screenreader → kann nicht gefälscht
    werden ohne die Seite für Blinde zu brechen (illegal in vielen Ländern).
  → AX-Tree zeigt ALLE interaktiven Elemente → auch Shadow-DOM Elemente.
  → Google OAuth Buttons sind im Shadow-DOM → CDP sieht sie nicht,
    CUA/AX sieht sie (weil Screenreader sie brauchen).

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  LoginVerifier                                                          │
  │  ├── check()               → Haupt-Methode: (pid, wid, logged_in)      │
  │  │   ├── list_windows()    → ALLE Fenster (via CuaAdapter)             │
  │  │   ├── sort by z_index   → Vorderstes Fenster zuerst                  │
  │  │   ├── Filter: height>100 → Kein Menü/Dock                           │
  │  │   ├── Filter: chrome     → Nur Chrome-Fenster                         │
  │  │   ├── Check 1: "abmelden" in title? → SOFORT True                    │
  │  │   ├── Check 2: title ambiguous? → get_tree() + "abmelden" prüfen    │
  │  │   └── Kein Match? → (None, None, False)                              │
  │  └── CuaAdapter (injected) → Low-Level CUA Zugriff                     │
  └─────────────────────────────────────────────────────────────────────────┘

TWO-STAGE VERIFICATION:
  Stage 1 (Fast): Prüfe Fenster-Titel auf "abmelden".
    → Wenn Titel "abmelden" enthält → SOFORT eingeloggt (True).
    → Sehr schnell: Kein AX-Tree Scan nötig.
    → 90% der Fälle: Fenster-Titel zeigt "abmelden" wenn eingeloggt.

  Stage 2 (Slow): Wenn Titel unklar ("heypiggy", "verdienen", "dashboard"),
    scanne den AX-Tree nach "abmelden".
    → AX-Tree Scan ist langsamer (alle Elemente parsen).
    → Nur wenn Stage 1 unklar ist.
    → Fängt Edge-Cases ab (Fenster-Titel nicht aktualisiert).

WARUM z_index Sortierung?
  → Höherer z_index = Fenster ist weiter vorne.
  → Wenn mehrere Chrome-Fenster offen → das vorderste ist wahrscheinlich
    das aktive HeyPiggy Dashboard.
  → reverse=True → höchster z_index zuerst.

WARUM "heypiggy", "verdienen", "dashboard" als ambiguous Keywords?
  → Diese Keywords erscheinen im Fenster-Titel EINGELOGGT und AUSGELOGGT.
  → Beispiel: "HeyPiggy Dashboard - Dein Account" (egal ob Login-State).
  → Nur wenn Title AMBIGUOUS ist → wir müssen AX-Tree scannen.
  → WARUM nicht immer AX-Tree scannen? Langsamer. Stage 1 ist schneller.

BANNED METHODS (NIEMALS verwenden):
  ❌ DOM.querySelector("#logout") → Shadow-DOM blockiert Zugriff.
  ❌ CDP Runtime.evaluate("document.querySelector(...)") → Gleiches Problem.
  ❌ URL prüfen (/dashboard) → URL ändert sich nicht bei Login-State.
  ❌ Cookie-Prüfung allein → Cookies können abgelaufen/gelöscht sein.
  ❌ Screenshot + OCR → langsam, unzuverlässig, ressourcenintensiv.

WARUM Tuple[Optional[int], Optional[int], bool]?
  → (pid, wid, logged_in)
  → pid = Prozess-ID (für spätere CUA-Operationen).
  → wid = Fenster-ID (für spätere CUA-Operationen).
  → logged_in = Boolean (True/False).
  → Wenn nicht gefunden: (None, None, False).
  → Aufrufer kann direkt: if logged_in: ... verwenden.
  → WARUM Optional[int]? Wenn kein Chrome-Fenster gefunden → pid/wid = None.

WARUM (None, None, False) statt Exception?
  → Kein Chrome-Fenster = normaler Zustand (Chrome nicht gestartet).
  → Exception würde Flow abbrechen → nicht nötig.
  → GoogleOAuthFlow prüft: if logged_in → return already_logged_in.
  → Wenn nicht → starte Login-Prozess.

ABHÄNGIGKEITEN:
  • survey.auth.cua_adapter.CuaAdapter (für CUA-Zugriff).
  • macOS (CUA ist Apple-spezifisch).
  • cua-driver Binary im PATH.

TESTBARKEIT:
  → Mock CuaAdapter:
    mock = MagicMock()
    mock.list_windows.return_value = [
      {"pid": 123, "window_id": 456, "title": "abmelden", ...}
    ]
    verifier = LoginVerifier(mock)
    pid, wid, logged_in = verifier.check()
    # logged_in = True
  → KEIN echtes Chrome nötig für Unit-Tests.

WARNUNG:
  Diese Klasse ist MACOS-ONLY. Unter Linux/Windows schlägt sie fehl
  (cua-driver nicht verfügbar, keine CUA API).
================================================================================"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# __future__: Ermöglicht | Union Syntax (str | None) in Python < 3.10.
from __future__ import annotations

# typing: Type Hints für IDE-Autovervollständigung und mypy.
# Tuple: Wir geben (pid, wid, logged_in) als Tuple zurück.
# Optional: pid und wid können None sein (wenn kein Fenster gefunden).
from typing import Tuple, Optional

# CuaAdapter: Low-Level Wrapper für cua-driver Binary.
# WARUM relative Import (.cua_adapter)? Gleiches Paket, stabiler bei Refactoring.
from .cua_adapter import CuaAdapter


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: LoginVerifier
# ═══════════════════════════════════════════════════════════════════════════════
class LoginVerifier:
    """Erkennt ob HeyPiggy Dashboard eingeloggt ist via CUA/AX-Tree.
    
    WARUM eigene Klasse (nicht Funktion)?
      → Dependency Injection: CuaAdapter kann gemockt werden.
      → Wiederverwendbar: Einmal erstellen, mehrmals prüfen.
      → State: CuaAdapter wird zwischen Aufrufen wiederverwendet.
      → Testbarkeit: Mock CuaAdapter → keine echte macOS Umgebung nötig.
    
    WARUM nicht statisch?
      → Statische Funktionen können nicht gemockt werden (ohne monkeypatching).
      → Instanz-Methode → einfacher zu testen (Dependency Injection).
    
    LEBENSZYKLUS:
      1. Erstellen: verifier = LoginVerifier()  # oder LoginVerifier(mock_adapter)
      2. Prüfen:    pid, wid, ok = verifier.check()
      3. Wiederverwenden: pid, wid, ok = verifier.check()  # erneut prüfen
    
    PERFORMANCE:
      → list_windows(): ~1-2s (alle Fenster scannen).
      → Stage 1 (Titel-Check): ~0ms (kein extra Aufruf).
      → Stage 2 (AX-Tree): ~2-5s (wenn nötig).
      → Gesamt: 1-2s (meistens) bis 3-7s (selten).
    """

    def __init__(self, cua: Optional[CuaAdapter] = None):
        """Initialisiere LoginVerifier.
        
        WARUM Optional[CuaAdapter]?
          → Wenn None → erstellt einen neuen CuaAdapter (Standard-Use-Case).
          → Wenn gesetzt → verwendet den übergebenen (für Tests/Mocking).
          → Pattern: Dependency Injection mit Default.
        
        WARUM Default-Timeout von CuaAdapter (15s)?
          → list_windows() braucht 1-2s.
          → get_tree() braucht 2-5s.
          → 15s deckt beides ab.
          → Wenn langsamer → Timeout → (None, None, False).
        
        Args:
            cua: Optionaler CuaAdapter. None = neuen erstellen.
        
        Example:
            # Standard-Use-Case (echtes Chrome)
            verifier = LoginVerifier()
            
            # Mit Mock (für Tests)
            mock_adapter = MagicMock()
            verifier = LoginVerifier(mock_adapter)
        """
        # WARUM cua or CuaAdapter()? Lazy-Initialisierung.
        # Wenn cua=None → CuaAdapter() wird erst JETZT erstellt (nicht beim Import).
        # WARUM Instanz-Attribut? Wiederverwendung zwischen check() Aufrufen.
        self.cua = cua or CuaAdapter()

    def check(self) -> Tuple[Optional[int], Optional[int], bool]:
        """Prüfe ob HeyPiggy eingeloggt ist.
        
        ABLAUF (Two-Stage Verification):
          Stage 1 (Fast-Path):
            1. Liste alle Fenster via CuaAdapter.list_windows().
            2. Sortiere nach z_index (höchster zuerst, vorderstes Fenster).
            3. Für jedes Fenster:
               a. Filter: height > 100 (kein Menü/Dock/Popup).
               b. Filter: app_name enthält "chrome" (nur Chrome).
               c. Check 1: Wenn Titel "abmelden" enthält → SOFORT True.
                  → Return: (pid, wid, True)
               d. Check 2: Wenn Titel "heypiggy"/"verdienen"/"dashboard" enthält
                  → AMBIGUOUS → weiter zu Stage 2.
          
          Stage 2 (AX-Tree Scan, nur bei ambiguous):
            4. Für ambiguous Fenster: get_tree() aufrufen.
            5. Prüfe ob EINE Zeile "abmelden" enthält.
            6. Wenn ja → (pid, wid, True).
          
          Stage 3 (Nicht gefunden):
            7. Wenn nichts gefunden → (None, None, False).
        
        WARUM Two-Stage?
          → Stage 1 ist schnell (nur Titel-Strings vergleichen).
          → 90% der Fälle: Titel zeigt "abmelden" → SOFORT Ergebnis.
          → Stage 2 ist langsamer (AX-Tree Scan) → nur wenn nötig.
          → Optimierung: Durchschnittliche Prüfzeit ~1-2s statt ~3-7s.
        
        WARUM z_index Sortierung (reverse=True)?
          → Höherer z_index = Fenster ist weiter vorne (sichtbarer).
          → Wenn mehrere Chrome-Fenster offen → vorderstes ist wahrscheinlich
            das aktive Dashboard (nicht ein Hintergrund-Tab).
          → WARUM nicht nur aktives Fenster? CUA listet ALLE Fenster,
            nicht nur das aktive.
        
        WARUM "abmelden" in title (nicht nur AX-Tree)?
          → Fenster-Titel wird von Chrome gesetzt (nicht von JavaScript).
          → Titel ist zuverlässiger als DOM (DOM kann manipuliert werden).
          → Schneller: Kein extra CUA-Aufruf nötig.
          → Wenn HeyPiggy Dashboard "abmelden" anzeigt → Chrome setzt das
            oft in den Fenster-Titel (für Tab-Übersicht).
        
        WARUM height > 100?
          → macOS hat viele kleine Fenster (Menüleiste, Dock, Popups).
          → Diese haben height < 100 (oft 20-40 Pixel).
          → Browser-Fenster haben height > 500.
          → Filter entfernt ALLE nicht-Browser-Fenster.
          → WARUM 100? Konservativ. Entfernt Menüleiste aber behält kleine Browser.
        
        WARUM "chrome" in app_name.lower()?
          → app_name kommt von macOS: "Google Chrome", "Safari".
          → Wir wollen NUR Chrome (nicht Safari, Firefox, andere Apps).
          → .lower() für Case-Insensitivität.
        
        WARUM "heypiggy", "verdienen", "dashboard" als ambiguous?
          → Diese Keywords erscheinen in Titel eingeloggt und ausgeloggt.
          → Beispiel: "HeyPiggy Dashboard" → könnte eingeloggt oder nicht sein.
          → Nur wenn der Titel diese Keywords enthält (aber nicht "abmelden")
            → wir müssen den AX-Tree scannen.
          → Wenn Titel "Google" oder "Anmelden" → ausgeloggt → kein Scan nötig.
        
        WARUM return bei erstem Match?
          → Wir geben beim ersten Treffer zurück.
          → Bei mehreren Chrome-Fenstern → erstes passende (vorderstes).
          → Wenn nichts passt → (None, None, False).
        
        WARUM Tuple[Optional[int], Optional[int], bool]?
          → (pid, wid, logged_in)
          → pid/wid = None wenn kein passendes Fenster gefunden.
          → logged_in = True wenn "abmelden" gefunden.
          → Aufrufer kann: if logged_in and wid: ...
          → WARUM nicht nur bool? Aufrufer braucht pid/wid für weitere CUA-Aufrufe.
        
        Returns:
            (pid, wid, logged_in):
            - pid: Prozess-ID des Chrome (oder None).
            - wid: Fenster-ID (oder None).
            - logged_in: True wenn "abmelden" gefunden, sonst False.
        
        Example:
            verifier = LoginVerifier()
            pid, wid, is_logged_in = verifier.check()
            
            if is_logged_in and wid:
                print(f"Eingeloggt! pid={pid}, wid={wid}")
            else:
                print("Nicht eingeloggt oder Chrome nicht gefunden")
        """
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 1: Alle Fenster auflisten
        # ═══════════════════════════════════════════════════════════════════
        # WARUM list_windows()? Wir müssen ALLE Fenster sehen um Chrome zu finden.
        # WARUM nicht nur aktives Fenster? CUA kennt "aktives Fenster" nicht.
        #   Wir müssen alle durchsuchen und das richtige finden.
        windows = self.cua.list_windows()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 2: Nach z_index sortieren (vorderstes zuerst)
        # ═══════════════════════════════════════════════════════════════════
        # WARUM sortieren? Wenn mehrere Chrome-Fenster offen → das vorderste
        #   ist wahrscheinlich das aktive Dashboard (nicht Hintergrund-Tab).
        # WARUM reverse=True? Höchster z_index zuerst (vorne = höherer Index).
        # WARUM key=lambda? Wir extrahieren z_index aus dem Fenster-Dict.
        # WARUM .get("z_index", 0)? Wenn z_index fehlt → 0 (hinten).
        windows.sort(key=lambda w: w.get("z_index", 0), reverse=True)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 3: Durch alle Fenster iterieren
        # ═══════════════════════════════════════════════════════════════════
        # WARUM for-Schleife? Wir suchen das ERSTE passende Fenster.
        # Wenn mehrere passen → vorderstes (wegen Sortierung) gewinnt.
        for w in windows:
            # Extrahiere bounds (Fenster-Größe).
            # WARUM .get("bounds", {})? Wenn bounds fehlt → leeres Dict → height=0.
            b = w.get("bounds", {})
            
            # Extrahiere Titel (lowercase für Case-Insensitive Matching).
            # WARUM .lower()? "Abmelden", "ABMELDEN", "abmelden" → alle matchen.
            t = (w.get("title") or "").lower()
            
            # Extrahiere App-Name (lowercase).
            # WARUM .get("app_name") or ""? Wenn app_name fehlt → leerer String.
            n = (w.get("app_name") or "").lower()
            
            # Extrahiere PID.
            # WARUM .get("pid")? Wenn pid fehlt → None → später geprüft.
            pid = w.get("pid")
            
            # ═══════════════════════════════════════════════════════════════
            # FILTER 1: Höhe muss > 100 sein
            # ═══════════════════════════════════════════════════════════════
            # WARUM height > 100? Entfernt Menüleiste, Dock, Popups.
            # WARUM .get("height", 0)? Wenn height fehlt → 0 → abgelehnt.
            if b.get("height", 0) < 100:
                # Nicht-Browser-Fenster überspringen.
                continue
            
            # ═══════════════════════════════════════════════════════════════
            # FILTER 2: Muss Chrome sein
            # ═══════════════════════════════════════════════════════════════
            # WARUM "chrome" in n? Nur Chrome-Fenster (nicht Safari, Firefox).
            # WARUM .lower() bereits gemacht? n ist bereits lowercase.
            if "chrome" not in n:
                # Kein Chrome → überspringen.
                continue
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 1: STRONG Indicator — "abmelden" im Titel
            # ═══════════════════════════════════════════════════════════════
            # WARUM zuerst? Schnellster Check, kein extra CUA-Aufruf.
            # "abmelden" im Fenster-Titel → sehr zuverlässiger Indicator.
            # Chrome setzt oft Dashboard-Titel in Fenster-Titel.
            if "abmelden" in t:
                # EINGELOGGT! Sofort zurückgeben.
                # WARUM return (nicht break)? Wir haben unser Ergebnis.
                # pid und wid sind verfügbar → sofort return.
                return pid, w.get("window_id"), True
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 2: AMBIGUOUS — Titel ist unklar → AX-Tree scannen
            # ═══════════════════════════════════════════════════════════════
            # WARUM ambiguous? Wenn Titel "HeyPiggy" oder "Dashboard" enthält
            #   → könnte eingeloggt ODER ausgeloggt sein.
            #   → Wir müssen den AX-Tree scannen um sicher zu sein.
            # WARUM nur diese 3 Keywords? Erfahrungswerte aus tatsächlichen Tests.
            #   - "heypiggy": Titel enthält immer "HeyPiggy" (egal ob Login).
            #   - "verdienen": Deutscher Titel "Mit HeyPiggy verdienen".
            #   - "dashboard": Titel enthält "Dashboard".
            if any(k in t for k in ["heypiggy", "verdienen", "dashboard"]):
                # ═══════════════════════════════════════════════════════════
                # AX-Tree Scan
                # ═══════════════════════════════════════════════════════════
                # WARUM get_tree()? Wir müssen ALLE Elemente der Seite prüfen.
                # Der AX-Tree enthält ALLE Accessibility-Elemente (inkl. Shadow-DOM).
                tree = self.cua.get_tree(pid, w.get("window_id"))
                
                # Prüfe ob EINE Zeile "abmelden" enthält.
                # WARUM any()? Wir wollen nur wissen OB es existiert (nicht wo).
                # WARUM l.lower()? l ist eine Zeile aus dem AX-Tree.
                #   "abmelden" könnte als "Abmelden" oder "abmelden" erscheinen.
                if any("abmelden" in l.lower() for l in tree):
                    # "abmelden" im AX-Tree gefunden → EINGELOGGT!
                    return pid, w.get("window_id"), True
                
                # Wenn nicht "abmelden" im AX-Tree → wahrscheinlich ausgeloggt.
                # Aber: Wir geben nicht False zurück → wir prüfen weitere Fenster.
                # WARUM? Mehrere Chrome-Fenster → vielleicht ist ein anderes das
                #   eingeloggte Dashboard (z.B. anderer Tab).
                # Also: continue → nächstes Fenster prüfen.
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 4: Nichts gefunden
        # ═══════════════════════════════════════════════════════════════════
        # Wenn wir hier ankommen → kein passendes Fenster gefunden.
        # Mögliche Gründe:
        #   - Chrome läuft nicht.
        #   - Chrome hat kein HeyPiggy Dashboard offen.
        #   - User ist ausgeloggt (kein "abmelden" gefunden).
        # WARUM (None, None, False)? Einheitliches Format (immer 3 Werte).
        #   Aufrufer kann: pid, wid, ok = verifier.check() → if ok: ...
        return None, None, False
