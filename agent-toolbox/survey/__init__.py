"""================================================================================
survey/ — Survey-Automation Subpackage
================================================================================

ZWECK:
  Enthält ALLE Module für die HeyPiggy Survey-Automation.
  Dieses Paket ist ein self-contained Subpackage von agent-toolbox.
  Es wird von api/main.py lazy-geladen (nur wenn Login/Survey-Endpoints aufgerufen
  werden).

WARUM separates Subpackage?
  → Kapselung: Survey-Logik ist getrennt von API/Schemas/Core.
  → Lazy-Loading: api/main.py importiert survey/ nur bei Bedarf.
  → Testbarkeit: survey/ kann unabhängig von FastAPI getestet werden.
  → Wiederverwendung: survey/ Module können auch außerhalb der API verwendet
    werden (z.B. CLI-Tools, Scripts).

STRUKTUR:
  survey/
  ├── __init__.py          ← DU BIST HIER: Paket-Doku (keine Imports)
  ├── auth/                ← Google OAuth Login (CUA-basiert)
  │   ├── __init__.py      ← Public API: CuaAdapter, LoginVerifier, GoogleOAuthFlow
  │   ├── cua_adapter.py   ← CUA-Driver Subprocess Wrapper
  │   ├── login_verifier.py← Login-State Detection via AX-Tree
  │   └── google_oauth.py  ← 6-Step OAuth Flow
  ├── security/            ← Credential Resolution (SecretsClient)
  │   └── __init__.py      ← SecretsClient, CPXCredentials, MissingSecretError
  └── chrome.py            ← Chrome Lifecycle Manager (Launch, Kill, CDP)

WARUM keine Imports in __init__.py?
  → Dieses Paket hat KEINE öffentliche API auf Paket-Ebene.
  → Clients importieren aus Submodulen:
    from survey.auth import GoogleOAuthFlow
    from survey.security import SecretsClient
    from survey.chrome import ChromeLauncher
  → Keine zentrale __all__ nötig (die ist in survey.auth.__init__.py).

WARUM auth/ und security/ als Subpackages?
  → auth/ = Authentication/Authorization (Login-Flow).
  → security/ = Credential Storage/Resolution (Secrets, API-Keys).
  → Trennung der Zuständigkeiten (Separation of Concerns).
  → security/ könnte später erweitert werden (Encryption, Vault, etc.).

LAZY-LOADING:
  → api/main.py importiert survey/ Module NICHT beim Startup.
  → Erst bei Aufruf von POST /services/heypiggy/login (mode="cua") wird
    survey.auth geladen.
  → Erst bei Aufruf von Chrome-Start wird survey.chrome geladen.
  → Vorteil: API startet schneller (kein Import-Overhead).

ABHÄNGIGKEITEN (Extern):
  → survey.auth: cua-driver Binary (macOS-only).
  → survey.security: pyyaml (für config.yaml Parsing).
  → survey.chrome: websocket-client (für CDP WebSocket).

BANNED:
  → Keine hardcoded Credentials (alles via SecretsClient).
  → Keine Playwright-Imports in survey/ (Playwright ist in core/).
  → Keine CDP-Klicks für Google OAuth (Shadow-DOM blockiert CDP).
================================================================================"""
