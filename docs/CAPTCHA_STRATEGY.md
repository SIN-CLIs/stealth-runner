# Captcha-Strategie — Eigene Solver + Open-Source, KEINE Bezahldienste

> **Policy (SR-260, 2026-05-17)**: Das Repo darf NIEMALS einen
> kostenpflichtigen Captcha-Solver-Service (2Captcha, Capsolver,
> AntiCaptcha, NextCaptcha, Death-by-CAPTCHA, etc.) integrieren. Auf
> Auftrag des Repo-Owners. Diese Datei ist die Single Source of Truth
> wie Captchas trotzdem geloest werden.

---

## Status-Matrix (2026-05-17)

| Captcha-Typ | Eigener Solver | OSS-Empfehlung | Status |
|---|---|---|---|
| Slide / Click-Slider | `stealth-captcha/solver/slide.py` | — | **OK** (in Production-Use) |
| Drag-Drop (Angular CDK) | `stealth-captcha/solver/drag_drop_angular.py` | — | **OK** (in Production-Use) |
| Drag-Drop (HTML5) | `stealth-captcha/solver/drag_drop.py` | — | **OK** |
| Text/OCR | `stealth-captcha/solver/text.py` | Lokales Pixtral / Whisper (audio) | **OK** mit lokalem Modell |
| **hCaptcha** | TBD | [QIN2DIM/hcaptcha-challenger](https://github.com/QIN2DIM/hcaptcha-challenger) | **Roadmap** |
| **reCAPTCHA v2** | TBD | Audio-Challenge + lokales Whisper (OSS) | **Roadmap** |
| **reCAPTCHA v3** | nicht loesbar | — | **Skip-by-design**: nur Browser-Trust-Score, mit Patchright + injection.js bereits 0.7+ erreichbar |
| **Cloudflare Turnstile** | nicht loesbar als Token-Solve | — | **Skip-by-design**: reines Trust-Score-Captcha, keine Klick-Loesung; Patchright haerten + iterativer Reload |
| **GeeTest v3/v4** | TBD (Slide-Variante mit existing slide.py adaptierbar) | — | **Roadmap** |
| **FunCaptcha (Arkose)** | unloesbar OSS | — | **Skip-by-design**: Survey wird abgebrochen |
| **Lemin Cropped** | TBD | — | **Roadmap** |

**Wenn ein Captcha-Typ als "Roadmap" oder "Skip-by-design" markiert ist
und im Live-Run auftritt**, liefert der Captcha-Adapter
`reason="solver_not_yet_bridged"` oder `reason="no_solver_for_type"`,
der LangGraph-Loop bricht den Survey ab und schreibt den Eintrag in den
DLQ. Wir bezahlen keinen Cent dafuer — wir akzeptieren stattdessen den
Skip.

---

## Empfohlene OSS-Repos (zur Inspiration / Fusion)

### hCaptcha — [QIN2DIM/hcaptcha-challenger](https://github.com/QIN2DIM/hcaptcha-challenger)

- **Lizenz**: GPL-3.0 (kompatibel — wir koennen einzelne Module
  vendoren, muessen aber bei Distribution die GPL respektieren).
- **Architektur**: Lokales YOLO-Modell fuer "Klicke alle Bilder mit X" +
  Reasoning-LLM (lokal oder via Gateway) fuer "Welche Reihenfolge
  zeigt korrekt Y → Z → A?".
- **Integration**: Als Submodule unter `stealth-captcha/vendor/hcaptcha-challenger/`,
  Adapter in `stealth-captcha/solver/hcaptcha.py`, Bridge in
  `survey-cli/survey/captcha_adapters.py::hcaptcha_solve`.

### reCAPTCHA Audio — [dessant/buster](https://github.com/dessant/buster)

- **Lizenz**: MIT.
- **Architektur**: Browser-Extension die den "Audio-Challenge"-Button
  klickt, das MP3 herunterlaedt, mit Speech-to-Text loest und den Text
  in das Antwortfeld schreibt.
- **Integration**: Wir extrahieren die JS-Logik (audio download +
  transcription orchestration) und nutzen lokales **Whisper**
  (`whisper.cpp` oder OpenAI-Whisper-OSS) als STT-Backend. Kein
  Cloud-Call.

### Slide / GeeTest — bereits eigen geloest

`stealth-captcha/solver/slide.py` deckt klassische Slide-Captchas ab.
GeeTest-v3-Slide laeuft mit minimaler Adaption. GeeTest-v4 (mit
"Click die Reihenfolge" / "Drehe das Bild") braucht ein Vision-Modell
— hier kann der hcaptcha-challenger-YOLO-Stack wiederverwendet werden.

### Browser-Trust-Score / Turnstile

Cloudflare Turnstile und reCAPTCHA-v3 sind **keine** Klick-Captchas. Sie
bewerten den Browser-Trust-Score. Loesung:

- **Patchright** (in #236 gemerged) eliminiert die wichtigsten
  CDP-Detection-Vektoren auf Binary-Level.
- **`injection.js`** (14 Module + Error.stack-Sanitizer in SR-259)
  patcht runtime-side die verbleibenden Fingerprints.
- **Trust-Score-Probing**: vor dem Survey-Start einmal pro Persona auf
  einer harmless-Seite Trust ergattern (z.B. wikipedia.org laden,
  scrollen, 30s warten) — dann ist das Survey-Captcha mit hoher
  Wahrscheinlichkeit "easy".

Wenn der Trust-Score zu niedrig ist und Turnstile uns einen Click-Box
gibt: **wir klicken nicht**. Stattdessen reload + fresh persona +
proxy-rotation.

---

## Implementierungs-Reihenfolge (Roadmap)

1. **hCaptcha** (haeufigster Captcha-Typ auf Heypiggy-Surveys).
   Entscheidung benoetigt: Submodule-Vendoring oder eigenes
   Reimplementing? **Empfehlung**: Submodule mit fixiertem Commit-Hash.
2. **reCAPTCHA Audio-Route** (zweithaeufigster, OSS-Loesung gut
   verstanden).
3. **GeeTest v4** (selten, niedriger ROI).
4. **FunCaptcha / Arkose** — *bewusst nicht implementieren*. Surveys mit
   FunCaptcha sind in der Regel hochsensible (e.g. Banken-Onboarding-
   Studien) und nicht der Use-Case des Repos.

---

## Wenn ein Captcha-Skip akzeptabel ist

Heypiggy-Surveys sind in der Regel mit ~0.10€ - 2.00€ vergueteten Tasks.
Ein Captcha-Skip kostet uns die Verguetung dieses einen Surveys. Eine
2Captcha-Loesung wuerde ca. 0.005-0.01€ pro Captcha kosten — bei
mehreren Captchas pro Survey schnell den ROI auffressen. Plus: wir
finanzieren keine Anti-Bot-Eskalation, indem wir bezahlen.

**Entscheidung des Repo-Owners ist final**: lieber 30% weniger Surveys,
aber 100% in Eigenleistung loesen.

---

## Verstoss-Detektion

Eine CI-Regel im Repo verbietet den Begriff `2captcha`, `capsolver`,
`anticaptcha`, `nextcaptcha`, `deathbycaptcha` in jedem neuen Commit
(Banned-Pattern-Check). Falls ein zukuenftiger Agent das wieder
einbauen will, schlaegt der Pre-Commit-Hook fehl. Siehe
`scripts/check_banned_patterns.py`.
