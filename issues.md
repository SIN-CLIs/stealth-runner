# issues.md — stealth-runner

## 🔴 PRIO 1 — EUR verdienen
- [ ] Google-Login mit zukunftsorientierte.energie@gmail.com abschließen
- [ ] Survey-Pipeline live testen: Dashboard → Screening → EUR
- [ ] Auszahlung testen

## 🟡 PRIO 2 — screen-follow ausbauen
- [ ] Audio-Aufnahme (Systemton)
- [ ] GUI-Vorschaufenster
- [ ] Multi-Display-Unterstützung

## 🟢 PRIO 3 — Releases
- [ ] git tag v0.1.0 auf stealth-runner
- [ ] git tag v0.3.0 auf screen-follow
- [ ] OpenSSF Badge für alle 7 Repos

## ⚪ PRIO 4 — Fehlende Survey-Module (angelegt, ungetestet)
- [ ] question-ranking — Drag & Drop simulieren
- [ ] question-opentext — Vision-LLM oder Templates
- [ ] question-slider — hold-Befehl testen
- [ ] question-audiovideo — Play/Pause + Wartezeit
- [ ] question-imagechoice — Bildauswahl

## ⚪ PRIO 5 — HeyPiggy-Plattform
- [ ] heypiggy-profile-update (Adresse, Interessen)
- [ ] heypiggy-payout (Auszahlung anfordern)
- [ ] heypiggy-survey-history (Welche bereits gemacht?)
- [ ] Auto-Refresh wenn keine Umfragen verfügbar

## ✅ Fertig
- [x] AXPress-Klick (CGEventPostToPid ersetzt)
- [x] VoiceOver-Trick (Chrome Accessibility)
- [x] type-Command (CGEvent Unicode Keyboard)
- [x] hold-Command (Cloudflare Turnstile)
- [x] 8 atomare heypiggy-CLIs
- [x] 4 Stealth-Skills (google-login, heypiggy-survey, openssf-badge, 4 modules)
- [x] screen-follow v0.2.1 (EventBus, Recording, Audit)
- [x] Profile-System (profiles/jeremy.yaml)
- [x] 23 MD-Dokumentationsdateien
- [x] GitHub CI + Release-Workflows
- [x] workspace.yaml in allen 5 Repos
- [x] CODEOWNERS, SUPPORT, Issue/PR-Templates
- [x] /doctor Skill SOTA v3

## 🔵 PRIO 6 — Security Hardening
- [ ] Google-Passwort in macOS Keychain statt YAML
- [ ] Chrome mit `--temp-profile` (flüchtig) für Survey-Sessions
- [ ] screen-follow-Aufnahmen in verschlüsseltes Volume
- [ ] SHA-256 Prüfsumme über Brain-Dateien
- [ ] Audit-Log aller CLI-Aufrufe (Wer hat wann was gemacht?)

## 🔵 PRIO 7 — Autonomous Daemon
- [ ] 24/7-Betrieb ohne manuellen Eingriff
- [ ] `stealth-runner daemon start` — läuft im Hintergrund
- [ ] Automatisches Session-Recovery bei Crash
- [ ] Benachrichtigung bei Captcha/2FA (Telegram/Discord)
- [ ] Auto-Restart nach Timeout

## 🔵 PRIO 8 — SaaS API
- [ ] FastAPI-Wrapper um stealth-runner
- [ ] `POST /api/v1/survey/start`
- [ ] `GET /api/v1/earnings`
- [ ] Rate-Limiting + Auth
