# SR-27 — stealth-suite: Incident Resolution + Monitoring

| Feld | Wert |
|------|------|
| Status | 🟡 IN PROGRESS |
| Priority | 🟡 Medium |
| Created | 2026-05-05 |
| Labels | documentation, stealth-suite, incidents |

---

## Kontext

Mehrere kritische Findings und Resolutions aus der stealth-suite Arbeit:

1. **Captcha-Dispatch Bug** — dispatchEvent (isTrusted:false) + CGEvent (Hit-Test blocked) → CDP Input.dispatchMouseEvent
2. **Hardcoded NVIDIA_API_KEY** in `vision/verify.py` → Environment-Variable
3. **BOT vs USER Chrome Verwechslung** —kill-Kommandos müssen exakte Patterns nutzen
4. **CUA-ONLY Trinity** — skylight-cli BANNED, nur noch cua-driver

---

## Ziel

**Vor Annahme:** Alle Findings sind in `stealth-suite/incidents/` als Markdown dokumentiert mit:
- Root Cause
- Solution
- Prevention
- Betroffene Files

---

## Akzeptanzkriterien

### incidents/ Verzeichnis
- [ ] `stealth-suite/py-packages/incidents/` existiert
- [ ] `2026-05-05-captcha-solved-cdp.md` — dispatchEvent → CDP Resolution ✅ (already done)
- [ ] `2026-05-05-hardcoded-api-key-vision.md` — NVIDIA_API_KEY Security Fix
- [ ] `2026-05-05-chrome-kill-patterns.md` — BOT vs USER Chrome Kill Patterns
- [ ] `2026-05-05-cua-only-trinity.md` — CUA-only Architektur Enforcement

### stealth-suite/issues.md
- [ ] Eigenes `stealth-suite/issues.md` mit Verweis auf `/issues/` im stealth-runner
- [ ] Alle stealth-suite-spezifischen Issues hier getrackt
- [ ] Status: DONE / IN PROGRESS / BLOCKED pro Issue

---

## Incident Template

```markdown
# [KURZTITEL] — [Was passiert ist]

| Feld | Wert |
|------|------|
| Severity | 🔴 Critical / 🟠 High / 🟡 Medium |
| Status | 🟡 IN PROGRESS |
| Date | YYYY-MM-DD |

## Summary
1-2 Sätze.

## Root Cause
Was war der technische Grund?

## Solution
Was wurde gemacht?

## Prevention
Was verhindert Wiederholung?

## Files Affected
- List of files changed
```

---

## Geschätzter Aufwand

- **Time**: 1h (Dokumentation)
- **Difficulty**: Niedrig
- **Blocker**: Keine
