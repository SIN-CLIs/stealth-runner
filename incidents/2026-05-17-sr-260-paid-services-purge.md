# 2026-05-17 — SR-260: Paid-Services Purge (2Captcha + Capsolver + OpenAI)

## Sachverhalt

Repo-Owner stellte fest, dass das Repo **gegen seine ausdrueckliche
Anforderung** kostenpflichtige Services integriert hatte:

  1. **2Captcha-Solver** — vollstaendiges Modul `stealth-captcha/src/
     stealth_captcha/solver/twocaptcha.py` plus Bridge in
     `survey-cli/survey/captcha_adapters.py` plus Config-Knob in
     `core/config.py`.
  2. **Capsolver-Solver** — als Alternative im Config-Knob.
  3. **Direkter OpenAI-API-Key** — `make_openai_judge()` Factory in
     `survey-cli/survey/reliability/trajectory_judge.py` rief OpenAI
     direkt auf.
  4. **Beides als "warning"-Severity in `env_check.REQUIRED_FOR_LIVE_RUN`**
     gelistet — Operator sah keinen sofortigen Fail beim Start.

Das war ein klarer Verstoss gegen die Anforderung des Repo-Owners. Die
Integration kam ueber gemergte PRs der Welle-1+2 (vor SR-260) ins Repo
und wurde nicht abgefangen.

## Massnahme (SR-260)

Atomarer Cleanup-PR `fix/remove-paid-services-sr-260`:

### Geloescht
  - `stealth-captcha/src/stealth_captcha/solver/twocaptcha.py` (komplette Datei)
  - `tests/test_twocaptcha_solver.py` (komplette Datei)

### Refaktoriert (paid-service-Code raus, OSS-Pfad rein)
  - `stealth-captcha/src/stealth_captcha/solver/__init__.py` — keine Re-Exports
    der `TwoCaptchaFallbackSolver`-Symbole mehr; BANNED-METHODS-Block ergaenzt.
  - `survey-cli/survey/captcha_adapters.py` — der ganze 2Captcha-Block
    ersetzt durch `_not_bridged()`-Stubs fuer hcaptcha/recaptcha/turnstile.
    Roadmap-Kommentar verweist auf `docs/CAPTCHA_STRATEGY.md`.
  - `core/config.py` — `CaptchaConfig.twocaptcha_api_key` und `.capsolver_api_key`
    entfernt; `from_env()` liest nur noch `CAPTCHA_SOLVE_TIMEOUT_S`. Custom
    `__repr__` geloescht (nicht mehr noetig). Doc-Block aktualisiert.
  - `core/security.py` — Doku-Beispiele auf `ai_gateway` umgeschrieben.
  - `survey-cli/survey/reliability/env_check.py` — `REQUIRED_FOR_LIVE_RUN`
    enthaelt nur noch `AI_GATEWAY_API_KEY`. TWOCAPTCHA + OPENAI raus.
  - `survey-cli/survey/reliability/trajectory_judge.py` — neue
    `make_ai_gateway_judge()` Factory (Vercel AI Gateway via OpenAI-
    kompatible API). Alte `make_openai_judge` als deprecated alias
    behalten, der intern die gateway-Factory aufruft (BackCompat).
  - `survey-cli/survey/observability/redact.py` — `ai_gateway_api_key`
    zur Provider-spezifischen Pattern-Liste hinzugefuegt.
  - `tests/test_core_config.py` — `test_twocaptcha_api_key_redaction_safe`
    durch generischen `test_secret_repr_redaction_safe` ersetzt.
  - `survey-cli/tests/test_env_check.py` + `test_redact.py` — Test-Fixtures
    auf `AI_GATEWAY_API_KEY` umgestellt.

### Neu hinzugefuegt
  - `docs/CAPTCHA_STRATEGY.md` — Single Source of Truth fuer die
    Captcha-Strategie. Liste der unterstuetzten Captcha-Typen,
    Empfehlungen fuer OSS-Loesungen (hcaptcha-challenger, dessant/buster
    fuer reCAPTCHA Audio), Skip-by-design-Faelle, Implementierungs-
    Reihenfolge.
  - `scripts/check_banned_patterns.py` — neue Bans:
    `\b2captcha\b`, `\bcapsolver\b`, `\banticaptcha\b`, `\bnextcaptcha\b`,
    `\bdeathbycaptcha\b`, `\bTWOCAPTCHA_API_KEY\b`, `\bCAPSOLVER_API_KEY\b`,
    `\bOPENAI_API_KEY\b`, `\bANTHROPIC_API_KEY\b`. Doku/Comments sind
    durch tokenize-masking ausgenommen — diese Datei selbst und
    `docs/CAPTCHA_STRATEGY.md` triggern dadurch nicht.

### `.env.example`
  - TWOCAPTCHA_API_KEY und CAPSOLVER_API_KEY entfernt.
  - Neue Sektion "LLM BACKEND — VERCEL AI GATEWAY (NUR DIES!)":
    `AI_GATEWAY_API_KEY` und optionaler `AI_GATEWAY_BASE_URL`.
  - Policy-Header an Datei-Top: SR-260 explizit dokumentiert.

## Verifikation

```bash
$ python scripts/check_banned_patterns.py
  No banned patterns found.

$ python -m unittest scripts.tests.test_check_banned_patterns
  Ran 14 tests in 0.008s — OK

$ cd survey-cli && python -m unittest tests.test_env_check tests.test_redact \
    tests.test_circuit_breaker tests.test_rate_limit tests.test_full_stability \
    tests.test_personas_quarantine_ttl tests.test_dlq_health
  Ran 153 tests in 0.254s — OK
```

## Was NICHT geaendert wurde

  - **AGENTS.md Audit-History (Section 17)** — historischer Eintrag
    bleibt bestehen; er dokumentiert das damalige TWOCAPTCHA_API_KEY-
    Beispiel im env_check-Kontext. Kommentar/String → durch tokenize
    gemasked → kein Banned-Pattern-Treffer. Loeschen wuerde Audit-Trail
    zerstoeren.
  - **Existierende Solver in stealth-captcha/** (slide, drag_drop,
    drag_drop_angular, text) — nicht angefasst. Sind eigene Solver,
    keine bezahlten Services.
  - **`make_openai_judge` als deprecated alias** — bleibt importierbar,
    forwardet aber 100 % der Calls auf `make_ai_gateway_judge`. Damit
    bricht kein bestehender Caller.

## Folgemassnahmen (offen)

  1. **CAPTCHA_STRATEGY.md Roadmap umsetzen**: hcaptcha-challenger als
     Submodule vendoren; reCAPTCHA-Audio-Solver mit lokalem Whisper.
  2. **Pre-commit hook installieren** (`.pre-commit-config.yaml`
     existiert bereits) — der Banned-Pattern-Check muss bei jedem
     Commit laufen, sonst kann ein zukuenftiger Agent die paid services
     wieder einbauen.
  3. **`make_openai_judge`-Alias Deprecation-Schedule**: in 30 Tagen
     einen Deprecation-Warning hinzufuegen, in 60 Tagen entfernen.
  4. **Heypiggy-Live-Run**: validieren dass der Skip-Pfad bei
     hcaptcha/recaptcha/turnstile sauber funktioniert (Survey wird in
     den DLQ verschoben, nicht stuck).

## Audit-Trail Verstoss

Der Verstoss kam ueber Welle-2-Merges (Direct-Push-to-Main, dokumentiert
in `2026-05-17-welle-3-ceo-override-sweep.md`). Lessons:

  - **Direct-Push umgeht jeden Policy-Check**. Auch wenn der Banned-
    Pattern-Check existiert haette, waere er nicht gegen den Merge-
    Commit gelaufen.
  - **Owner-Anforderungen muessen ZWINGEND in `scripts/check_banned_patterns.py`
    stehen**, nicht nur in Memory eines Agents.
  - **Pre-existing-Code aus historischen PRs muss bei jeder Welle
    explizit auditiert werden**, nicht nur die neuen Diffs.

SR-260 schliesst diese Luecke. Banned-Pattern-Check ist jetzt der
Hard-Gate gegen erneute paid-service-Einfuehrung.
