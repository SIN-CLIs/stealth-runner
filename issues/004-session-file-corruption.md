# Issue #4: Session File Corruption — 2965 Sessions mit 2 Bytes (P1)

> **Status**: OPEN  
> **Severity**: 🟡 P1  
> **Reporter**: Automated Analysis  
> **Erstellt**: 2026-05-08 00:20 UTC  
> **Betroffene Dateien**: `~/.local/share/opencode/sessions/`, `~/.stealth/sync_events.jsonl`

---

## Problem-Beschreibung

`~/.local/share/opencode/sessions/` enthält **2965 Dateien** — **jeweils nur 2 Bytes**:
```
-rw-r--r-- 1 user staff 2 May 7 22:21 ses_2b2910ccaffeEx6F9BLRg4SWdo.json
-rw-r--r--r-- 1 user staff 2 May 7 22:21 ses_2b28c324fffetpGvQm7jjVbUPM.json
```

**2 Bytes** = wahrscheinlich `{}` oder leerer JSON → **keine Session-Daten**.

**Impact**: Keine Session-History, keine Fehleranalyse möglich, keine "Lern-Daten" für den Agent.

---

## Root-Cause-Analyse

### Hypothese 1: Session-Write wird nicht abgeschlossen
Sessions werden erstellt (Datei angelegt) aber nie beschrieben.
→ Programm crasht vor `f.write()` oder `json.dump()`.

### Hypothese 2: Cleanup zu aggressiv
Ein Cleanup-Job löscht Session-Daten aber behält leere Dateien.
→ Warum? Vielleicht um Session-IDs zu tracken ohne Daten zu speichern.

### Hypothese 3: Falsches Write-Format
```python
# ❌ BAD: Write JSON als String, nicht als Bytes
f.write(json.dumps(data))  # → String in Binary mode?

# ✅ GOOD: Explicit JSON dump
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
```

### Hypothese 4: Opencode DB vs Files
Vielleicht werden Sessions primär in SQLite DB gespeichert und Dateien sind nur "Marker"?
→ Aber: 2965 Dateien mit 2 Bytes deutet auf Fehler hin, nicht Design.

---

## Vorgeschlagener Fix

### Fix 1: Session-Write Verification
```python
def write_session(session_id, data):
    """
    Schreibt Session-Daten mit Verifikation.

    WARUM Verifikation?
      2-Byte-Dateien entstehen wenn Write abgebrochen wird.
      → Nach dem Write: File-Größe prüfen, JSON validieren.
    """
    path = f"~/.local/share/opencode/sessions/{session_id}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    # VERIFY: File nicht leer
    size = os.path.getsize(path)
    if size < 100:  # Sinnvolle Session hat mindestens 100 Bytes
        raise SessionWriteError(
            f"Session {session_id} zu klein: {size} Bytes. "
            f"Erwartet: >100 Bytes. Daten: {json.dumps(data)[:200]}"
        )

    # VERIFY: Valid JSON
    try:
        with open(path, 'r') as f:
            loaded = json.load(f)
        assert loaded.get("session_id") == session_id
    except Exception as e:
        raise SessionWriteError(f"Session {session_id} ungültiges JSON: {e}")
```

### Fix 2: Session-Cleanup mit Backup
```python
def cleanup_old_sessions(max_age_days=7, backup_dir="~/.local/share/opencode/sessions/archive/"):
    """
    Löscht alte Sessions aber mit Backup.

    WARUM Backup?
      Wenn Session-Daten später doch noch nötig sind (Debugging, Audit).
    """
    cutoff = time.time() - (max_age_days * 86400)
    for filename in os.listdir(sessions_dir):
        path = os.path.join(sessions_dir, filename)
        if os.path.getmtime(path) < cutoff:
            # Backup vor Löschen
            shutil.move(path, os.path.join(backup_dir, filename))
            # Log
            print(f"[SESSION] Archived: {filename}")
```

---

## Akzeptanzkriterien

- [ ] Sessions haben sinnvolle Größe (>100 Bytes)
- [ ] Session-Write wird verifiziert (Größe + JSON-Validität)
- [ ] Alte Sessions werden archiviert (nicht gelöscht)
- [ ] Monitoring: Alert wenn leere Sessions entstehen
- [ ] Test: `test_session_write_verification` muss passen

---

**Nächster Schritt**: Session-Write-Flow analysieren + Verification implementieren.

*Letzte Aktualisierung: 2026-05-08 00:20 UTC*
