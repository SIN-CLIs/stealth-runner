"""================================================================================
survey/auth/__init__.py — Auth Package Public API
================================================================================

ZWECK:
  Zentrale Export-Stelle für ALLE Authentication-Module.
  Client-Code importiert NUR aus diesem Paket — nie aus Submodulen direkt.

WARUM zentrale __init__.py?
  → Kapselung: Interne Struktur (cua_adapter.py, google_oauth.py) kann sich
    ändern ohne Clients zu brechen.
  → Einfacher Import: from survey.auth import GoogleOAuthFlow (statt
    from survey.auth.google_oauth import GoogleOAuthFlow).
  → Einheitliche API: Alle Auth-Klassen kommen aus EINEM Namespace.

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  survey.auth (Dieses Paket)                                             │
  │  ├── __init__.py        ← DU BIST HIER: Public API                      │
  │  ├── cua_adapter.py     ← CuaAdapter: CUA-Driver Wrapper              │
  │  ├── login_verifier.py  ← LoginVerifier: Session-Prüfung              │
  │  └── google_oauth.py    ← GoogleOAuthFlow + LoginResult: 6-Step OAuth   │
  └─────────────────────────────────────────────────────────────────────────┘

EXPORTIERTE KLASSEN:
  • CuaAdapter      — Low-Level CUA-Driver Wrapper (subprocess → cua-driver).
  • LoginVerifier   — Prüft "abmelden" im AX-Tree → Session gültig?
  • GoogleOAuthFlow — Führt 6-Step Google OAuth aus (Email → Weiter → Fortfahren).
  • LoginResult     — Dataclass: status, pid, wid, reason.

WARUM diese 4 Klassen?
  → CuaAdapter: Isoliert ALLE cua-driver Aufrufe (einfacher zu mocken/testen).
  → LoginVerifier: Separat vom Flow → kann unabhängig Session prüfen.
  → GoogleOAuthFlow: Orchestration der 6 Steps → klare Fehler-Reasons pro Step.
  → LoginResult: Typsicheres Ergebnis (nicht nur True/False).

WARUM KEINE SecretsClient hier?
  → SecretsClient ist in survey/security/ → getrennte Zuständigkeit.
  → Auth = Flow-Logik, Security = Credential-Resolution.
  → Vermischung = Credential-Leaks in Git (wenn auth.py hardcoded Werte hätte).

BANNED PATTERNS (NIEMALS in diesem Paket verwenden):
  ❌ Hardcoded PIDs (71104, etc.) → PIDs sind dynamisch, immer frisch suchen.
  ❌ pkill -f "Google Chrome" → tötet USER Chrome!
  ❌ killall Google Chrome → tötet ALLE Chrome.
  ❌ CDP für Google OAuth Klicks → Shadow-DOM blockiert CDP.
  ❌ Playwright für Google OAuth → funktioniert nicht bei Shadow-DOM.

VERWENDUNG:
  from survey.auth import GoogleOAuthFlow, LoginVerifier, CuaAdapter, LoginResult

  # WICHTIG: PIDs sind dynamisch! Niemals hardcoded verwenden!
  # Chrome PID dynamisch ermitteln via CDP:
  #   import urllib.request, json
  #   tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json').read())
  #   chrome_pid = next((t['processId'] for t in tabs if 'heypiggy' in t.get('url','')), None)

  flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
  result = flow.execute(pid=chrome_pid)  # <- dynamische PID, NICHT 35970!
  # result.status == "ok" | "already_logged_in" | "error"
  # result.reason gibt bei error die konkrete Fehlerursache.

ABHÄNGIGKEITEN:
  • cua-driver Binary (brew install cua-driver oder manuell installiert).
  • macOS Accessibility API (nur auf macOS verfügbar).
  • survey/security/SecretsClient (für GOOGLE_EMAIL).

WARNUNG:
  Dieses Paket funktioniert NUR auf macOS!
  CUA (Core UI Automation) ist Apple-spezifisch.
  Unter Linux/Windows → LoginVerifier und GoogleOAuthFlow schlagen fehl.
================================================================================"""

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM relative Imports (.cua_adapter statt survey.auth.cua_adapter)?
# → Relative Imports sind stabiler bei Refactoring (Dateien können verschoben werden).
# → Absolute Imports (survey.auth.cua_adapter) brechen wenn das Paket umbenannt wird.
# → . bedeutet "dieses Paket" (survey.auth).

# CuaAdapter: Low-Level Wrapper für cua-driver Binary.
# WARUM zuerst? Abhängigkeit der anderen Klassen (LoginVerifier braucht CuaAdapter).
from .cua_adapter import CuaAdapter

# LoginVerifier: Prüft Login-State via AX-Tree.
# WARUM zweite? Hängt von CuaAdapter ab, aber ist unabhängig von GoogleOAuthFlow.
from .login_verifier import LoginVerifier

# GoogleOAuthFlow: Haupt-Logik für 6-Step OAuth.
# LoginResult: Dataclass für Ergebnis.
# WARUM zusammen? Beide kommen aus google_oauth.py, sind konzeptionell verbunden.
from .google_oauth import GoogleOAuthFlow, LoginResult

# ═══════════════════════════════════════════════════════════════════════════════
# __all__: Explizite Export-Liste
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM __all__?
# → from survey.auth import * importiert NUR diese 4 Namen.
# → Schützt vor versehentlichem Export interner Hilfsfunktionen.
# → Wenn jemand from survey.auth import SOME_INTERNAL_FUNC macht → NameError.
# → Das ist Python's "public API contract".
__all__ = [
    "CuaAdapter",       # Low-Level: cua-driver subprocess wrapper
    "LoginVerifier",    # Session-Check: "abmelden" im AX-Tree?
    "GoogleOAuthFlow",  # Orchestration: 6-Step Google OAuth
    "LoginResult",      # Ergebnis-Dataclass: status, pid, wid, reason
]
