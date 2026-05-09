# Issue #3: Chrome Startup — Korrekte Flags werden nicht erzwungen (P0)

> **Status**: OPEN  
> **Severity**: 🔴 P0  
> **Reporter**: Automated Analysis  
> **Erstellt**: 2026-05-08 00:20 UTC  
> **Betroffene Dateien**: `cli/modules/auto_google_login.py`, `cli/modules/session_manager.py`, `survey-cli/survey.py`

---

## Problem-Beschreibung

Chrome MUSS mit diesen Flags gestartet werden:
```bash
--force-renderer-accessibility      # Für cua-driver AX-Tree
--remote-allow-origins="*"          # Für CDP WebSocket (MIT Anführungszeichen!)
--remote-debugging-port=9999        # Für CDP
--user-data-dir="/tmp/chrome-jeremy-heypiggy-9999"  # Profil 901 Kopie
```

**Aktuelle Probleme**:
1. `playstealth launch` setzt **NICHT** `--force-renderer-accessibility` → AX-Tree leer
2. `--remote-allow-origins=*` (ohne Quotes) → zsh expandiert `*` → `--remote-allow-origins=file1 file2 ...` → Chrome startet nicht korrekt
3. Frisches Profil in `/tmp/heypiggy-new-*` → **KEINE Cookies**, Login nötig!
4. Profile 902 Kopie → **VERSCHLÜSSELTE Cookies**, Login nötig!

---

## Root-Cause-Analyse

### Ursache 1: playstealth launch ist BANNED aber wird trotzdem verwendet
`auto_google_login.py` verwendet `SessionManager.launch()` — was intern `playstealth` nutzt?
→ Wenn ja: Accessibility Flag fehlt.

### Ursache 2: Kein Post-Start Check
Nach Chrome-Start wird nicht verifiziert:
- `curl http://127.0.0.1:9999/json` → CDP erreichbar?
- `cua-driver call list_windows` → AX-Tree hat Elemente?
- Chrome-Prozess hat `--force-renderer-accessibility` in Kommandozeile?

### Ursache 3: Falscher Profile-Weg
```python
# ❌ BAD: Frisches Profil → keine Cookies, Login nötig!
profile = f"/tmp/heypiggy-new-{int(time.time())}"

# ❌ BAD: Profil 902 Kopie → verschlüsselte Cookies, Login nötig!
profile = "/tmp/chrome-instance-B"

# ✅ GOOD: Profil 901 (Jeremy) Kopie + Cookie-Injection
import shutil, os
profile_dir = "/tmp/chrome-jeremy-heypiggy-9999"
if os.path.exists(profile_dir):
    shutil.rmtree(profile_dir)
shutil.copytree(
    os.path.expanduser("~/Library/Application Support/Google Chrome/Profile 901 (Jeremy)"),
    profile_dir
)
# → DANN: 7 HeyPiggy-Cookies aus ~/.stealth/heypiggy-backup/ injectieren
```

---

## Vorgeschlagener Fix

### ChromeLauncher Klasse
```python
class ChromeLauncher:
    """
    Sicheres Chrome-Launching mit Flag-Validierung.

    BANNED in dieser Klasse:
      ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
      ❌ --remote-allow-origins=* (ohne Quotes)
      ❌ ~/tmp/chrome-instance-B (fixed profile)
      ❌ Hardcoded PIDs
    """

    REQUIRED_FLAGS = [
        "--force-renderer-accessibility",
        '--remote-allow-origins="*"',  # MIT Quotes!
        "--remote-debugging-port=9999",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    def launch(self, url="https://heypiggy.com/?page=dashboard"):
        """
        Startet Chrome mit korrekten Flags + Verifikation.

        Returns:
            {"status": "ok", "pid": int, "profile": str, "flags_verified": bool}
            {"status": "error", "reason": str, "missing_flags": list}
        """
        # 1. Profil 901 (Jeremy) kopieren
        import shutil
        profile = "/tmp/chrome-jeremy-heypiggy-9999"
        if os.path.exists(profile):
            shutil.rmtree(profile)
        shutil.copytree(
            os.path.expanduser("~/Library/Application Support/Google Chrome/Profile 901 (Jeremy)"),
            profile
        )

        # 2. Chrome BINARY Pfad finden
        chrome_binary = self._find_chrome_binary()
        if not chrome_binary:
            return {"status": "error", "reason": "chrome_binary_not_found"}

        # 3. Kommando zusammenbauen
        cmd = [
            chrome_binary,
            f'--user-data-dir="{profile}"',
            *self.REQUIRED_FLAGS,
            url,
        ]

        # 4. Chrome starten
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = proc.pid

        # 5. WARTEN bis Chrome bereit (nicht sofort return!)
        time.sleep(3)

        # 6. Verifikation: CDP erreichbar?
        if not self._verify_cdp_reachable():
            proc.terminate()
            return {"status": "error", "reason": "cdp_not_reachable_after_3s"}

        # 7. Verifikation: AX-Tree hat Elemente?
        if not self._verify_ax_tree_has_elements(pid):
            proc.terminate()
            return {"status": "error", "reason": "ax_tree_empty", "hint": "--force-renderer-accessibility missing?"}

        # 8. Verifikation: Flags in Kommandozeile?
        missing = self._verify_flags_in_cmdline(pid)
        if missing:
            return {"status": "warning", "pid": pid, "profile": profile, "missing_flags": missing}

        return {"status": "ok", "pid": pid, "profile": profile, "flags_verified": True}

    def _verify_cdp_reachable(self, port=9999, timeout=10):
        """Prüft ob CDP http://127.0.0.1:9999/json erreichbar ist."""
        import urllib.request
        for _ in range(timeout):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1)
                return True
            except:
                time.sleep(1)
        return False

    def _verify_ax_tree_has_elements(self, pid, timeout=10):
        """Prüft ob cua-driver list_windows Elemente zurückgibt."""
        for _ in range(timeout):
            try:
                r = subprocess.run(
                    ["cua-driver", "call", "list_windows"],
                    capture_output=True, text=True, timeout=5
                )
                d = json.loads(r.stdout)
                windows = d.get("windows", [])
                if any(w.get("bounds", {}).get("height", 0) > 100 for w in windows):
                    return True
            except:
                pass
            time.sleep(1)
        return False

    def _verify_flags_in_cmdline(self, pid):
        """Prüft ob Required Flags in /proc/<pid>/cmdline (Linux) oder ps (macOS) sind."""
        import psutil  # oder: ps aux | grep PID
        try:
            proc = psutil.Process(pid)
            cmdline = " ".join(proc.cmdline())
            missing = []
            for flag in self.REQUIRED_FLAGS:
                if flag not in cmdline:
                    missing.append(flag)
            return missing
        except Exception:
            return ["unknown — psutil failed"]
```

---

## Akzeptanzkriterien

- [ ] Chrome startet NIEMALS ohne `--force-renderer-accessibility`
- [ ] Chrome startet NIEMALS ohne `--remote-allow-origins="*"` (MIT Quotes)
- [ ] Profile ist IMMER Profil 901 (Jeremy) Kopie → `/tmp/chrome-jeremy-heypiggy-9999`
- [ ] Post-Start: 7 HeyPiggy-Cookies MÜSSEN injectiert werden (Backup: `~/.stealth/heypiggy-backup/heypiggy-cookies.json`)
- [ ] Post-Start Check: CDP erreichbar nach max 10s
- [ ] Post-Start Check: "Abmelden" in body.innerText sichtbar?
- [ ] Wenn Verifikation fehlschlägt: Chrome wird beendet + Error-Reason

---

**Nächster Schritt**: `ChromeLauncher` implementieren + alle Launch-Points ersetzen.

*Letzte Aktualisierung: 2026-05-08 00:20 UTC*
