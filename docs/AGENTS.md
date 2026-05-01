# AGENTS.md — IDIOTENSICHER (NUR EIN BEFEHL)

## WENN DU NUR EINEN KLICK TESTEN WILLST

```bash
python3 runner/safe_click.py $(playstealth launch (isolierte PID)" | head -1)
```

Das holt ALLE Elemente von skylight-cli, nimmt die AX-Frame-Koordinaten,
und klickt den ersten Web-Button per `--element-index`.

## WENN DU DEN GANZEN RUNNER STARTEN WILLST

```bash
python3 main.py "https://heypiggy.com/?page=dashboard"
```

## WAS DU NIEMALS TUST

- ❌ --x oder --y Koordinaten raten (das Apple-Menü ist bei 0,0!)
- ❌ Fenster-Position + Element-Position addieren (AX-Frame ist ABSOLUT)
- ❌ Auf (500,600) klicken weil "das ist die Mitte" (ist es nicht)
- ❌ Irgendwas mit "Fenster-Mitte" berechnen
