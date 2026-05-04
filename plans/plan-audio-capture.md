# PLAN: Audio-Capture Integration — BlackHole + ffmpeg + Omni in survey_runner

> **Quelle:** `audio_capture.py` (364 Zeilen), `audio_box.py` (156 Zeilen), `survey_runner.py`  
> **Abhängigkeiten:** Keine (Module existieren, kein neues Repo nötig)  
> **Priorität:** 🟡 HOCH  
> **Aufwand:** Klein

---

## 🔍 Recherche-Ergebnisse

| Komponente | Datei | Status | Details |
|-----------|-------|--------|---------|
| Audio Detection | `audio_box.py:18-42` | ✅ | CDP-basiert: `<video>`/`<audio>` + Text-Scan |
| Audio Capture (BlackHole) | `audio_capture.py:41-108` | ✅ | SwitchAudioSource → ffmpeg → WAV |
| Omni Audio Analysis | `audio_capture.py:111-219` | ✅ | base64-WAV an NVIDIA NIM senden |
| Integration in survey_runner | `survey_runner.py:36-98` | ⚠️ | Code existiert, `_detect_audio_question()` + `_handle_audio_question()` sind da |
| SIP Check Automation | — | ❌ Fehlt | `csrutil status` muss automatisch geprüft werden |
| BlackHole Install | — | ❌ Fehlt | Automatische Installationsanleitung bei Bedarf |
| **Pipeline-Check** | `audio_capture.py:222+` | ✅ | `check_audio_pipeline()` existiert |

---

## 🎯 Ziel

Audio-Module in `survey_runner.py` aktivieren: Detektion → BlackHole-Umschaltung → ffmpeg Capture → Omni Analyse → Antwort.

## ✅ Sub-Tasks

### Phase 1: Setup automatisieren
- [ ] `check_audio_pipeline()` in `survey_runner._handle_audio_question()` integrieren
- [ ] Bei fehlendem BlackHole: automatische Installationsanleitung ausgeben
- [ ] SIP-Status prüfen und dokumentieren

### Phase 2: Integration in Survey Flow
- [ ] `_detect_audio_question()` vor jeder Frage aufrufen
- [ ] Bei Audio: `_handle_audio_question()` aufrufen
- [ ] Antwort aus Omni in den normalen Antwort-Form-Flow einspeisen

### Phase 3: Fehlerbehandlung
- [ ] Timeout bei Audio-Aufnahme (max 10s)
- [ ] Fallback: Wenn Omni keine Antwort liefert → Survey disqualifizieren
- [ ] Logging: Audio-Fragen + Antworten loggen

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/audio_capture.py` | BlackHole + ffmpeg Audio Capture (364 Zeilen) |
| `cli/modules/audio_box.py` | simplified API (156 Zeilen) |
| `cli/modules/survey_runner.py` | Integration hier |

## 🔗 Issue

[ISSUE-SR-15: Audio-Capture Integration](../issues/ISSUE-SR-15.md)
