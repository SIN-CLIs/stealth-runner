# Plan 07: Auto-Login Hardening

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 4  
> **Priority**: P0

## Ziel

Google OAuth Login wird ein testbares Auth-Module mit kleiner Interface. `cli/modules/auto_google_login.py` bleibt hoechstens Kompatibilitaetswrapper.

## Aktueller Schaden

`cli/modules/auto_google_login.py` ist ein 1700+ Zeilen Monolith und enthaelt nach Analyse zwei `execute()` Definitionen. Das ist ein schlechtes Public Interface:

- Shadowing-Risiko.
- CUA subprocess, Window-Findung, Regex-Parsing, Email, State-Verifikation und Fallbacks gemischt.
- Schwer zu testen.
- Schwer zu refactoren, ohne Login zu brechen.

## Ziel-Module

```text
survey-cli/survey/auth/
  __init__.py
  google_oauth.py       # GoogleOAuthFlow
  login_verifier.py     # dashboard logged-in detection
  oauth_window.py       # OAuth window detection
  cua_adapter.py        # tiny wrapper over cua-driver CLI
  keychain_fallback.py  # Keychain/Password fallback
```

## Ziel-Interface

```python
class GoogleOAuthFlow:
    def execute(self, pid: int | None = None, url: str | None = None) -> LoginResult:
        """Login or verify existing login. Never touches user Chrome."""

class LoginVerifier:
    def is_logged_in(self, pid: int, wid: int) -> bool:
        """Detect dashboard login state from CDP/AX text."""

class CuaAdapter:
    def list_windows(self) -> list[Window]
    def get_tree(self, pid: int, wid: int) -> str
    def click(self, pid: int, wid: int, idx: int, verify: bool = True) -> CuaResult
    def set_value(self, pid: int, wid: int, idx: int, value: str) -> CuaResult
```

## Flow

1. Verify invariants: Chrome bot lease, cua daemon healthy, AX tree non-empty.
2. Check already logged in.
3. Find HeyPiggy window.
4. Click Google login link.
5. Detect OAuth window.
6. Fill configured email from `SecretsClient`.
7. Continue via Keychain or password fallback.
8. Final consent.
9. Verify dashboard logged-in state.
10. Return structured `LoginResult`.

## Arbeitsschritte

1. Duplicate `execute()` Situation eindeutig klaeren und Tests schreiben.
2. `CuaAdapter` extrahieren, subprocess parsing dort kapseln.
3. `LoginVerifier` extrahieren.
4. `OAuthWindowDetector` extrahieren.
5. `GoogleOAuthFlow` bauen.
6. `auto_google_login.py` auf Wrapper reduzieren.
7. Email nur ueber `SecretsClient.get_google_email()`.
8. Keychain-Fallback als expliziter Fehlerpfad oder Implementation.

## Tests

| Test | Erwartung |
|---|---|
| already logged in | kein Google-Klick |
| fresh OAuth | alle Schritte in Reihenfolge |
| OAuth window missing | sauberer Fehler, kein Retry-Spam |
| keychain auto fill | Fortfahren erkannt |
| password fallback | password field erkannt oder MissingSecretError |
| wrong window | kein Klick auf Apple-Menueleiste/Browser-Chrome |
| cua output text | `Performed`/`Set` Parser robust |

## Verification

```bash
rg "def execute" cli/modules/auto_google_login.py survey-cli/survey/auth --glob '*.py'
rg "zukunftsorientierte\.energie@gmail\.com" cli/modules/auto_google_login.py survey-cli/survey/auth --glob '*.py'
pytest survey-cli/tests/test_auto_google_login.py -q
```

## Exit-Kriterien

- Genau ein Login Public Interface.
- Kein hardcoded Email Default.
- Monolith ist Wrapper oder deutlich zerlegt.
- Login-Flow hat Step-Tests und live verification recipe.
