# Issue 009: git checkout -- KATASTROPHE — Permanenter Bann

> **Status**: ❌ KATASTROPHE PASSIERT  
> **Datum**: 2026-05-08 ~1778293606858  
> **Impact**: 78 Dateien revertet, ~200KB Code verloren  
> **Lösung**: BANNED in banned.md

---

## Was passierte

```bash
cd /Users/jeremy/dev/stealth-runner && \
git checkout -- agent-toolbox/api/main.py \
               agent-toolbox/api/schemas.py \
               agent-toolbox/api/survey_actions.py
```

Dieser Befehl hat **ALLE uncommitted changes** in diesen 3 Files revertet — ohne Unterschied zwischen "gut" und "schlecht".

### Was verloren ging:

| File | Session-Version | Nach git checkout |
|------|----------------|-------------------|
| `survey_actions.py` | 93KB (mit Fixes) | 111KB (alter Stand) |
| `main.py` | 69KB (survey_tools Router) | 63KB (ohne Router) |
| `schemas.py` | 79KB (neue Klassen) | 87KB (alter Stand) |

**Resultat**: FastAPI konnte nicht starten, Imports fehlten.

---

## Warum ist das besonders schlimm?

1. **Session-Writes waren inkonsistent** — survey_actions.py erwartete Klassen die schemas.py nicht hatte
2. **Keine Zeit zum Committen** — Die Änderungen waren Work-in-Progress
3. **Kaskadeneffekt** — Backup-Restore versuchte session-Version, aber die war kaputt
4. **Manuelle Rekonstruktion nötig** — 5 Fragmente aus Session-DB extrahiert

---

## Die Lösung: ABSOLUTER BANN

### banned.md (bereits hinzugefügt):

```markdown
## 2026-05-09: git checkout -- BANNED

**GRUND**: Atomische Zerstörung aller uncommitted changes.
**ALTERNATIVEN**:
- `git add -p` — Interaktives Hinzufügen (überprüfe jede Änderung)
- `git stash -p` — Interaktives Stashen (speichere für später)
- Manuelles Backup vorher: `cp file.py file.py.backup`
- `git diff > patch.diff` + `git checkout --` + selektives Anwenden

**WENN VERWENDET**:
→ SOFORT Session-DB prüfen ob Rekonstruktion möglich
→ NIE blind weiterarbeiten
```

---

## Recovery-Protokoll (falls jemand es doch macht)

### Schritt 1: NICHTS überschreiben
Sofort stoppen! Keine neuen Änderungen machen.

### Schritt 2: Session-DB durchsuchen
```python
import sqlite3
conn = sqlite3.connect('~/.local/share/opencode/opencode.db')
# Suche nach edit/write operations für die betroffenen Files
```

### Schritt 3: Rekonstruktion
```bash
python3 /tmp/reconstruct_from_session.py
```
→ Extrahiert 96 Files aus Session-DB

### Schritt 4: Vergleichen
```bash
diff /tmp/reconstructed/file.py /path/to/file.py
```

### Schritt 5: Backup erstellen
```bash
cp file.py file.py.backup.$(date +%s)
```

### Schritt 6: Selektiv restoren
NUR die fehlenden Teile zurückkopieren, nicht alles.

---

## Prevention

### Pre-Commit Hook (optional):
```bash
#!/bin/bash
# .git/hooks/pre-commit
if git diff --cached | grep -q "WIP\|TODO\|FIXME"; then
    echo "ERROR: WIP commits not allowed"
    exit 1
fi
```

### Automatisches Stashing (alle 5 Min):
```bash
while true; do
    git stash push -m "auto-$(date +%s)"
    sleep 300
done
```

---

## Session-Referenz

- Session: `ses_1fb699b0effeULfoLPQHb1rBpi`
- Timestamp: `prt_e0a9050eb0014likAG0kV2qikB`
- "git checkout -- hat survey_actions.py, main.py, schemas.py ALLE Änderungen verworfen"
- Recovery: `prt_e0a936fd20021Qg7Oj61ADE6wR` — 5 Fragmente rekonstruiert

---

## Links

- Issue 007: Erfolgreicher Survey-Durchlauf
- Issue 008: Endpoint-Architektur
- banned.md: Permanenter Verweis
