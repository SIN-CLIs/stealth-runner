# SR-113: `scripts/check_audit_log_schema.py` — schema-validator fuer audit-logs

**Status:** OPEN
**Owner:** Agent 3 (Quereinsteiger, API-only workflow)
**Spawned by:** v0-CEO-Session am 2026-05-12
**Parallel-safe with:** PR #100, #105, #110, #111, #101, #106, #112

---

## **NEUE-AGENT-ORIENTIERUNG** (lesen vor allem anderen)

### Was ist dieses Projekt?

`SIN-CLIs/stealth-runner` — Python-CLI fuer automatisierte Survey-Tests.
Innerhalb davon: `survey-cli/` = das Hauptpaket. Die `learn/` subdomain
ist eine ML-feedback-loop fuer pattern-discovery:

  1. **Suggester** generiert pattern-Vorschlaege (jsonl-records)
  2. **Reviewer** filtert sie via human review
  3. **Apply** schreibt approved-records in `FIELD_PATTERNS`
  4. **Apply** loggt jeden Record (applied OR rejected) in
     `survey-cli/logs/learn-applied-{ISO}.jsonl`

**Dein Task betrifft NUR die Audit-Logs aus Schritt 4.** Du musst NICHT
verstehen wie Suggester/Reviewer/Apply funktionieren — du validierst nur
ob die jsonl-records gegen eine fest definierte Schema-Spec passen.

### API-only workflow (KEINE lokale Repo-Clone!)

Du arbeitest komplett ueber die GitHub-REST-API mit dem token
`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` (commit-Push-Berechtigung).
Repo: `SIN-CLIs/stealth-runner`. Standard-Branch: `main`.

Reference-template fuer denselben workflow: **PR #110** (Kollege-Agent
hat `scripts/triage_stale_suggestions.py` via API ge-pusht — gleicher
shape, gleiche scripts/ surface, schaut mal als template).

Workflow-Steps:

  1. `GET /repos/.../git/refs/heads/main` → main-SHA
  2. `GET /repos/.../git/commits/{sha}` → base-tree-SHA
  3. Pro Datei: `POST /repos/.../git/blobs` mit base64-content → blob-SHA
  4. `POST /repos/.../git/trees` mit `base_tree` + neuen blob-paths
  5. `POST /repos/.../git/commits` mit commit-msg + tree-sha + parent
  6. `POST /repos/.../git/refs` mit `ref: refs/heads/<dein-branch>` und neue commit-sha
  7. `POST /repos/.../pulls` mit base=main, head=`<dein-branch>`

Optional: Tests lokal mit `python3 -m pytest scripts/tests/test_check_audit_log_schema.py` checken (kannst du tun aber muss nicht).

### Repo-Map (was du wissen musst)

```
SIN-CLIs/stealth-runner/
├── scripts/                          ← DEINE surface
│   ├── check_banned_patterns.py      ← reference impl: einzelner script
│   ├── check_doc_health.py
│   ├── check_submodules.py
│   ├── triage_stale_suggestions.py   ← SR-108: schau es als template an
│   └── tests/
│       ├── __init__.py
│       ├── test_check_banned_patterns.py  ← reference impl: tests
│       └── test_triage_stale_suggestions.py  ← SR-108 tests
├── survey-cli/
│   └── (alles hier UNCHANGED — touch nicht an)
├── _plans/
│   └── 113-check-audit-log-schema.md  ← DEIN plan-file, IM commit zu loeschen
└── AGENTS.md                          ← rule A4: plan-files werden im PR geloescht
```

---

## Zweck

`apply.py` schreibt audit-records in `logs/learn-applied-{ISO}.jsonl` mit
4 verschiedenen `decision`-Typen — und je nach decision-Typ unterschied-
lichen Pflichtfeldern. Wenn `apply.py` mal gepatcht wird und die schema
silently driftet (z.B. ein neues optionales Feld wird required, oder ein
Feld umbenannt), dann werden alle downstream-Tools (`audit`, `explain`,
`triage`, kuenftige) silently kaputt.

Dieses Script ist die **schema-guard**: laeuft als CI-step oder cron, prueft
jeden record gegen die spec, exit-non-zero wenn drift.

---

## Schema-Spec (komplett, copy-paste-bereit)

**Top-level required field** (jeder record):

  - `decision`: string, MUSS einer von:
      - `"applied"`
      - `"rejected_by_gate"`
      - `"rejected_by_reviewer"`
      - `"rejected_by_ast"`

**Bei `decision == "applied"`** zusaetzlich required:

  - `family`:     string, non-empty
  - `keyword`:    string, non-empty
  - `source`:     string, MUSS `"substring"` oder `"llm"`
  - `confidence`: number, 0.0 <= x <= 1.0
  - `timestamp`:  string, ISO-format parseable

Optional:

  - `model`:       string OR null (wenn source=="llm", sollte set sein —
                   aber das ist eine WARNING, kein ERROR)
  - `prompt_hash`: string OR null

**Bei `decision in {rejected_by_gate, rejected_by_ast}`** zusaetzlich required:

  - `reason`: string, non-empty
  - `entry`:  dict (validierung des entry siehe unten)

**Bei `decision == "rejected_by_reviewer"`** zusaetzlich required:

  - `entry`:  dict

(`reason` ist hier OPTIONAL — reviewer-rejects haben oft keinen reason.)

**`entry`-dict (wenn vorhanden)** muss enthalten:

  - `role`: string
  - `normalized_label`: string

Alle anderen entry-Felder sind opt-in (`suggested_family`, `source`,
`first_seen`, etc.) und werden NICHT vom Validator gepruefte (forward-
compat).

---

## Scope (exakt 2 neue Dateien)

| Datei | Status | Aenderung |
|---|---|---|
| `scripts/check_audit_log_schema.py` | NEU | Standalone read-only validator |
| `scripts/tests/test_check_audit_log_schema.py` | NEU | 10+ Tests |

KEINE Aenderung an `survey/`, `.github/workflows/`, `tests/`,
`pyproject.toml`, `requirements.txt`.

### CLI

```
python scripts/check_audit_log_schema.py
    [--logs DIR]                # default: survey-cli/logs
    [--input PATH]              # validate single jsonl
    [--exit-non-zero-on-error]  # CI-Mode: rc=1 wenn errors gefunden
    [--strict]                  # treat WARNINGs als ERRORs
    [--json]                    # JSON output instead of human
```

### Output (human, default)

```
[schema-check] scanning survey-cli/logs/learn-applied-*.jsonl
[schema-check] found 3 file(s), 142 record(s)

learn-applied-20260510T120000Z.jsonl (45 records):
  OK: 44
  WARN: 1
    record #7 (decision=applied): source="llm" but model is null

learn-applied-20260508T080000Z.jsonl (97 records):
  OK: 95
  ERROR: 2
    record #14 (decision=applied): confidence=1.5 out of range [0.0, 1.0]
    record #82: missing required field "decision"

Summary:
  Total OK:      139
  Total WARN:    1
  Total ERROR:   2

Exit code: 0 (use --exit-non-zero-on-error to flag errors via exit code)
```

### Output (`--json`)

```json
{
  "files_scanned": 3,
  "total_records": 142,
  "ok": 139,
  "warn": 1,
  "error": 2,
  "issues": [
    {"file": "learn-applied-20260510T120000Z.jsonl",
     "record_index": 7,
     "severity": "WARN",
     "message": "source=\"llm\" but model is null"},
    {"file": "learn-applied-20260508T080000Z.jsonl",
     "record_index": 14,
     "severity": "ERROR",
     "message": "confidence=1.5 out of range [0.0, 1.0]"},
    {"file": "learn-applied-20260508T080000Z.jsonl",
     "record_index": 82,
     "severity": "ERROR",
     "message": "missing required field \"decision\""}
  ]
}
```

---

## Architektur-Entscheidungen

**A) Standalone, kein survey-package-import.** scripts/-konvention.
`json`, `pathlib`, `argparse`, `glob` aus stdlib reicht. Keine externe lib.

**B) Validation-funktion pure.** `validate_record(rec: dict) -> List[Issue]`
returns list of issues (oder leere liste = ok). Macht Tests trivial.

**C) Default exit 0 (read-only diagnostic).** `--exit-non-zero-on-error`
fuer CI-mode. Mirror von SR-108 `--exit-non-zero-if-stale`.

**D) `--strict` upgradet WARN -> ERROR.** Nuetzlich fuer striktere
CI-policies wenn LLM-Records ohne model unerwuenscht sind.

**E) Pure stdout/stderr, KEINE files written.** Mock-builtins.open Test
zur Sicherheit.

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `survey/learn/*`
- KEINE Aenderung an `.github/workflows/*` (CI-Integration ist separates Issue)
- KEINE Aenderung an `pyproject.toml` / `requirements.txt`
- KEINE schema-extraction aus apply.py (schema ist hardcoded laut Spec oben — drift-detection ist genau der Punkt!)
- KEINE auto-fixing — READ-ONLY

---

## Acceptance Criteria

- [ ] `scripts/check_audit_log_schema.py` ist standalone executable
      (Shebang `#!/usr/bin/env python3` + chmod 755)
- [ ] CLI zeigt 5 Flags via `--help`
- [ ] Multi-file scan default `survey-cli/logs/learn-applied-*.jsonl`
- [ ] Single `--input PATH` override
- [ ] Decision must be one of 4 enum values (sonst ERROR)
- [ ] `decision=applied`: family/keyword/source/confidence/timestamp required (fehlend → ERROR)
- [ ] `source` must be substring|llm (sonst ERROR)
- [ ] `confidence` must be in [0.0, 1.0] (out-of-range → ERROR)
- [ ] `timestamp` muss ISO parseable sein (sonst ERROR)
- [ ] `decision=applied` + `source=llm` + `model is None/missing` → WARN
- [ ] reject-decisions: `entry` required (fehlend → ERROR)
- [ ] reject-decisions: `entry.role`, `entry.normalized_label` required
- [ ] `--exit-non-zero-on-error` exit 1 if errors > 0
- [ ] `--strict` upgradet WARN -> ERROR
- [ ] `--json` parseable
- [ ] 10+ Tests in `scripts/tests/test_check_audit_log_schema.py`
- [ ] Tests verwenden `tempfile.mkdtemp` + Cleanup
- [ ] Read-only audit (mock-open Test, optional aber empfohlen)
- [ ] Bestehende Tests bleiben gruen (zero regression)
- [ ] Closes #113 in commit-message
- [ ] `_plans/113-check-audit-log-schema.md` geloescht (rule A4) — DELETE wird im selben tree-update gemacht (siehe SR-108 commit als reference)

---

## Test Plan (mindestens 10 Tests)

1. **Empty input dir** → exit 0, total_records=0
2. **All records valid** → exit 0, errors=0
3. **Missing `decision` field** → ERROR
4. **Invalid `decision` value** ("foo") → ERROR
5. **`decision=applied` missing required** (z.B. `family`) → ERROR
6. **`source` invalid value** ("regex") → ERROR
7. **`confidence` out-of-range** (1.5, -0.1) → ERROR
8. **`timestamp` unparseable** ("not-a-date") → ERROR
9. **`decision=applied` + source=llm + model=null** → WARN (nicht ERROR)
10. **`--strict` upgradet WARN → ERROR** + `--exit-non-zero-on-error` triggert exit 1
11. **Reject record fehlend `entry`** → ERROR
12. **Reject record `entry` missing `role`/`normalized_label`** → ERROR

---

## File-Boundary-Matrix

| Surface | PR #100 | #105 | #101 | #106 | #110 | #111 | #112 | **#113** |
|---|---|---|---|---|---|---|---|---|
| `survey/*` | various | MOD | unchanged | MOD | unchanged | MOD | MOD | **unchanged** |
| `.github/workflows/*` | NEW | unchanged | NEW | unchanged | unchanged | unchanged | unchanged | **unchanged** |
| `scripts/triage_stale_suggestions.py` | unchanged | unchanged | unchanged | unchanged | NEW | unchanged | unchanged | **unchanged** |
| `scripts/check_audit_log_schema.py` | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | **NEW** |
| `tests/*` | NEW fixtures | unchanged | NEW | unchanged | unchanged | unchanged | unchanged | unchanged |
| `evals/*` | unchanged | unchanged | NEW | unchanged | unchanged | unchanged | unchanged | **unchanged** |

Konfliktrisiko = 0 mit allem.

---

## Reference: API-Workflow-Snippet

```bash
TOKEN="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"
API="https://api.github.com/repos/SIN-CLIs/stealth-runner"

# 1. main-SHA + base-tree-SHA
MAIN_SHA=$(curl -s -H "Authorization: token $TOKEN" "$API/git/refs/heads/main" | jq -r '.object.sha')
BASE_TREE=$(curl -s -H "Authorization: token $TOKEN" "$API/git/commits/$MAIN_SHA" | jq -r '.tree.sha')

# 2. Per Datei: blob hochladen (kann auch python-script lokal generieren)
upload_blob() {
  local b64=$(base64 -w0 < "$1")
  curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
    "$API/git/blobs" -d "{\"content\":\"$b64\",\"encoding\":\"base64\"}" | jq -r '.sha'
}
BLOB_SCRIPT=$(upload_blob /tmp/check_audit_log_schema.py)
BLOB_TEST=$(upload_blob /tmp/test_check_audit_log_schema.py)

# 3. Tree mit base + neue blobs + plan-file-delete (sha: null)
NEW_TREE=$(curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  "$API/git/trees" \
  -d "$(jq -nc --arg base "$BASE_TREE" --arg b1 "$BLOB_SCRIPT" --arg b2 "$BLOB_TEST" \
    '{base_tree: $base, tree: [
       {path: "scripts/check_audit_log_schema.py", mode: "100755", type: "blob", sha: $b1},
       {path: "scripts/tests/test_check_audit_log_schema.py", mode: "100644", type: "blob", sha: $b2},
       {path: "_plans/113-check-audit-log-schema.md", mode: "100644", type: "blob", sha: null}
     ]}')" | jq -r '.sha')

# 4. Commit
COMMIT=$(curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  "$API/git/commits" \
  -d "$(jq -nc --arg m "feat(scripts): SR-113 — audit-log schema validator. Closes #113." \
                --arg t "$NEW_TREE" --arg p "$MAIN_SHA" \
                '{message: $m, tree: $t, parents: [$p]}')" | jq -r '.sha')

# 5. Branch ref
curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  "$API/git/refs" \
  -d "$(jq -nc --arg sha "$COMMIT" '{ref: "refs/heads/feat/113-check-audit-log-schema", sha: $sha}')"

# 6. PR
curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  "$API/pulls" \
  -d '{"title":"feat(scripts): SR-113 — audit-log schema validator","body":"Closes #113.\n\n...","head":"feat/113-check-audit-log-schema","base":"main"}'
```

**Wichtig:** Bei der executable-script-Datei `mode: "100755"` (nicht `100644`) im tree-call — sonst kann das script nicht direkt aufgerufen werden.

---

## Estimated complexity

**XS-S** — single-file script (~180 LOC) + tests (~250 LOC). Identisches
shape wie SR-108 (`scripts/triage_stale_suggestions.py`, PR #110). One-PR-
cycle, kein cross-cutting.

---

## References

- **PR #110** — Kollege-Agent SR-108 `scripts/triage_stale_suggestions.py` — gleicher shape, **schau es dir als template an, bevor du anfaengst!**
- `survey-cli/survey/learn/apply.py` Zeilen 595-655 — origin der audit-record-writes (du brauchst es nicht zu modifizieren, nur als Referenz fuer schema-spec oben)
- `survey-cli/survey/learn/audit.py` (PR #111) — meine SR-109 docstring dokumentiert dasselbe schema (s. Modul-docstring)
- `AGENTS.md` rule A4 — plan-files muessen IM PR-commit geloescht werden
