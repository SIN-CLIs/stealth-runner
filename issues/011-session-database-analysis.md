# Issue 011: Session-Datenbank Analyse — Was gespeichert wird und was nicht

> **Status**: ✅ ANALYSIERT  
> **Datum**: 2026-05-09  
> **DB-Path**: `~/.local/share/opencode/opencode.db`  
> **Session**: `ses_1fb699b0effeULfoLPQHb1rBpi`  

---

## Datenbank-Struktur

### Tables (15 total):
```sql
__drizzle_migrations, project, message, part, permission, session, 
todo, session_share, control_account, account, account_state, 
event_sequence, event, workspace, session_message
```

---

## Was wird GESPEICHERT

### 1. message Table
- **Inhalt**: Metadaten nur (kein Text!)
- **Schema**: `id, session_id, time_created, time_updated, data`
- **data JSON**:
  ```json
  {
    "role": "assistant",
    "time": {"created": 1778193425690},
    "agent": "SIN-Zeus",
    "model": {"providerID": "fireworks-ai", "modelID": "kimi-k2p6"},
    "cost": 0.0708586,
    "tokens": {"total": 41751, "input": 39344, "output": 522}
  }
  ```
- **KEIN Text-Content** — nur Metadaten!

### 2. part Table
- **Inhalt**: Tool-Calls und AI-Antworten
- **Schema**: `id, message_id, session_id, time_created, time_updated, data`
- **data JSON** hat verschiedene `type`s:

| type | Inhalt | Häufigkeit |
|------|--------|------------|
| `text` | AI-Antwort (unser Gespräch!) | 392 von 17,599 |
| `tool` | Tool-Call (bash, edit, write) | ~2,600 |
| `reasoning` | AI-Interne Überlegungen | ~500 |
| `step-start` | Schritt-Beginn | ~500 |
| `step-finish` | Schritt-Ende | ~500 |

---

## Was wird NICHT gespeichert

### ❌ AI-Antworten in message Table
Die `message.data` enthält KEINEN `content` mit Text.
Der Text ist in den **Parts** versteckt.

### ❌ Datei-Inhalte
Nur `edit`/`write` Tool-Calls speichern `oldString`/`newString`.
Der AKTUELLE Datei-Stand ist nirgends gespeichert.

### ❌ Erfolgsberichte
"+0.15€ verdient" ist als `text` part gespeichert, aber:
- Schwer zu finden (mixed mit 17,000 anderen parts)
- Keine Struktur (plain text, nicht JSON)
- Kein Event-System für Erfolge

---

## Query-Beispiele

### Alle Text-Parts finden:
```sql
SELECT p.id, p.time_created, p.data
FROM part p
WHERE p.session_id = 'ses_1fb699b0effeULfoLPQHb1rBpi'
AND p.data LIKE '%"type":"text"%'
ORDER BY p.time_created DESC
```
→ 392 Ergebnisse

### Alle Edit-Operationen:
```sql
SELECT p.id, p.data
FROM part p
WHERE p.session_id = ?
AND p.data LIKE '%"tool":"edit"%'
```
→ 518 Ergebnisse

### Alle Write-Operationen:
```sql
SELECT p.id, p.data
FROM part p
WHERE p.session_id = ?
AND p.data LIKE '%"tool":"write"%'
```
→ 125 Ergebnisse

---

## Extraktions-Skript

```python
import sqlite3, json, os

conn = sqlite3.connect('~/.local/share/opencode/opencode.db')
c = conn.cursor()

session_id = 'ses_1fb699b0effeULfoLPQHb1rBpi'

# Alle parts laden
c.execute('''
    SELECT p.time_created, p.data
    FROM part p
    WHERE p.session_id = ?
    ORDER BY p.time_created ASC
''', (session_id,))

edits = []
writes = []
texts = []
for tc, data in c.fetchall():
    d = json.loads(data)
    if d.get('tool') == 'edit':
        edits.append({
            'time': tc,
            'file': d['state']['input']['filePath'],
            'old': d['state']['input']['oldString'],
            'new': d['state']['input']['newString']
        })
    elif d.get('tool') == 'write':
        writes.append({
            'time': tc,
            'file': d['state']['input']['filePath'],
            'content': d['state']['input']['content']
        })
    elif d.get('type') == 'text':
        texts.append({
            'time': tc,
            'text': d.get('text', '')
        })

print(f"Edits: {len(edits)}, Writes: {len(writes)}, Texts: {len(texts)}")
```

---

## Grenzen der Session-DB

### Was geht:
- Code-Änderungen rekonstruieren (edits/writes)
- Tool-Outputs lesen (bash Ergebnisse)
- AI-Antworten finden (text parts)

### Was NICHT geht:
- Aktuellen Datei-Stand wiederherstellen (nur Diffs)
- Konsistenten Zustand (edits sind nicht atomisch)
- Schnelle Suche (17,000+ parts, kein Full-Text-Index)
- Chat-Verlauf als Gespräch (parts sind verstreut)

---

## Empfehlung

**NIE auf Session-DB als Backup verlassen!**

Stattdessen:
1. `git commit` nach jeder funktionierenden Änderung
2. `git stash` vor gefährlichen Operationen
3. `cp file.py file.py.$(date +%s)` vor Experimenten
4. Issues erstellen für wichtige Erkenntnisse

---

## Session-Referenz

- Session: `ses_1fb699b0effeULfoLPQHb1rBpi`
- Parts: 17,599 total
- Text parts: 392
- Edit parts: 518
- Write parts: 125
- Bash parts: 1,932

---

## Links

- Issue 007: Erfolgreicher Survey-Durchlauf
- Issue 009: git checkout -- Katastrophe
