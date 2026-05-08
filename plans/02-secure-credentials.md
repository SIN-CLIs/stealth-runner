# Plan 02: Secure Credentials

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 3  
> **Priority**: P0  
> **Risk**: Niedrig technisch, hoch falls Secrets falsch rotiert werden.

## Ziel

Keine Credentials, PII oder API-Hashes als Code-Default. Secrets muessen fail-closed sein.

## Aktueller Stand

`survey-cli/survey/security/__init__.py` existiert und zentralisiert CPX-Werte. Das ist gut, aber die Implementation ist noch nicht sicher genug, weil Defaults im Code stehen:

```python
os.getenv("CPX_APP_ID", "11644")
os.getenv("CPX_EXT_USER_ID", "2525530")
os.getenv("CPX_SECURE_HASH", "...")
os.getenv("CPX_EMAIL", "...")
```

Auch `cli/modules/auto_google_login.py` hat noch einen `GOOGLE_EMAIL` Default.

## Problem

Env-var Defaults fuer echte Secrets sind keine Sicherheit. Sie sind nur Hardcoding an einer anderen Stelle.

## Ziel-Interface

```python
class SecretsClient:
    def get_cpx_credentials(self) -> CPXCredentials:
        """Return complete CPX credentials or raise MissingSecretError."""

    def get_google_email(self) -> str:
        """Return configured Google login email or raise MissingSecretError."""

    def get_nvidia_api_key(self) -> str:
        """Return NIM key or raise MissingSecretError."""
```

## Resolution Order

1. Environment variable.
2. Optional local secrets file outside repo, e.g. `~/.stealth/secrets.json`.
3. Optional Infisical/Vault adapter later.
4. Raise `MissingSecretError`.

Kein Fallback auf echte Werte.

## Arbeitsschritte

1. `MissingSecretError` einfuehren.
2. Alle echten Defaults aus `survey/security/__init__.py` entfernen.
3. `GOOGLE_EMAIL` Default in `auto_google_login.py` entfernen.
4. `.env.example` mit leeren Werten erstellen.
5. Tests anpassen: Testwerte werden per env fixture gesetzt.
6. `detect-secrets` Baseline erzeugen oder bewusst ohne Baseline starten.
7. Bekannte geleakte Werte aus Git-Historie bewerten und Credentials rotieren.

## Tests

| Test | Erwartung |
|---|---|
| no env | `MissingSecretError` |
| partial env | `MissingSecretError` mit fehlenden Keys |
| full env | `CPXCredentials` validiert |
| google email missing | fail-closed |
| tests use fixtures | keine echten Werte im Testcode ausser Dummywerte |

## Verification

```bash
rg "11644|2525530|ae75b0feca27c0f8eb356d7117d978ec|zukunftsorientierte\.energie@gmail\.com" . --glob '*.py'
python scripts/check_banned_patterns.py survey-cli cli run_survey.py
```

## Exit-Kriterien

- Keine echten CPX-/Google-Werte in Python-Code.
- Ohne Secrets startet kein Survey-Flow still mit Defaults.
- Tests nutzen Dummy-Secrets.
- CI fuehrt Secret-Scan aus.
