# graph-report-template.md — Template für Graphify Reports

> **Generiert am**: YYYY-MM-DD
> **Repo**: <repo-name>
> **Tool**: safishamsi/graphify

---

## Top-Level-Struktur

| Metrik | Wert |
|--------|------|
| Nodes gesamt | `<zahl>` |
| Edges gesamt | `<zahl>` |
| Communities | `<zahl>` |

## God Nodes (höchste Zentralität)

| Node | Rolle | Verbindungen |
|------|-------|-------------|
| `<node>` | `<beschreibung>` | `<zahl>` |

## Unerwartete Verknüpfungen

- `<node A>` ↔ `<node B>` — Grund: `<erklärung>`

## Empfehlungen

- [ ] God Nodes reduzieren (Single Points of Failure)
- [ ] Unerwartete Links prüfen (BANNED-Tool-Nutzung?)
- [ ] Neue Abhängigkeiten in brain.md dokumentieren

---

*Report generiert von graphify. Template: graph-report-template.md*
