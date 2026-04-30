# banned.md — Verbotene Patterns

## ❌ Absolut verboten
- **cua-driver** — ALT, ersetzt durch skylight-cli v0.2.0 (seit efd363f)
- **open -na "Google Chrome"** — Browser-Start NUR via playstealth-cli launch
- **AXStaticText klicken** — Nur AXButton, AXLink, AXCheckBox, AXRadioButton
- **Chrome DevTools Protocol (CDP)** — Direkter DOM-Zugriff
- **Chrome Extensions** — Keine Bridge/Extension
- **DOM-Manipulation** — Kein document.querySelector
- **Cursor-Stealing** — Kein CGEvent.post(tap: .cghidEventTap)
- **Unverschlüsselte Credentials** — .env NIE ins Repo

## ✅ Erlaubt (Stealth Triade)
- **skylight-cli** — Screenshot + Aktionen via SkyLight.framework
- **playstealth-cli** — Browser-Start mit Fingerprint-Schutz
- **unmask-cli** — Stealth-Verification
