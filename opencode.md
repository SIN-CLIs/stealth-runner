# opencode.md — OpenCode Konfiguration (Stealth Runner)

> **← [agents.md](agents.md) für Agenten-Verhalten**

---

## OpenCode Integration

Stealth Runner nutzt **OpenCode** als Agenten-Runtime.
Jedes Repo hat eine `.opencode/opencode.json` für Tool-Konfiguration.

### Konfiguration (`.opencode/opencode.json`)

```json
{
  "tools": ["cua-driver", "playstealth", "screen-follow"],
  "skills": ["cua-driver", "stealth-browser-operator", "sin-vision-colab"],
  "rules": {
    "pre_action": ["sinrules.md", "brain.md", "fix.md", "anti-learn.md"],
    "post_action": ["history.md", "changelog.md"]
  }
}
```

### Session-Start

```bash
# Neue Session starten
opencode -s stealth-runner

# Session fortsetzen
opencode -s <session-id>
```

**Letztes Update**: 2026-05-05
