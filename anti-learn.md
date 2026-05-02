# anti-learn.md – Anti-Patterns (was NIEMALS tun)

## ❌ Nur klicken ohne Texteingabe

Wenn eine Umfrage ein TEXTFELD zeigt (Einkommen, Alter, PLZ), DARF nicht einfach
"Go to next question" geklickt werden. Die Seite bleibt hängen, weil die Antwort fehlt.

**Korrekt**: Omni fragen: "Describe what you see. Any text fields?" → `type` Action ausführen.

## ❌ skylight-cli in Popup-Fenstern

skylight sieht NUR Hauptfenster. Popup-Element-Indices sind INVALID.

**Korrekt**: cua-driver mit `window_id`.

## ❌ PNG direkt an Omni senden (kein Resize)

1200×1006 PNG = 300KB → API timeout.

**Korrekt**: `img.thumbnail((960,960))` + JPEG quality=40.

## ❌ content ignorieren, nur reasoning lesen

Nemotron Omni schreibt JSON in `content`, Reasoning in `reasoning`.

**Korrekt**: Content priority vor reasoning.

## ❌ max_tokens=300 für Reasoning-Models

Reasoning braucht Tokens zum Denken. JSON kommt DANACH.

**Korrekt**: `max_tokens: 1000` in `config/vision_models.yaml`.

## ❌ bash mit & für Hintergrund-Prozesse

**Korrekt**: tmux `new-session -d` + `send-keys`.

## ❌ call_omo_agent (TOOL BROKEN)

9/9 Timeouts. Niemals nutzen.
