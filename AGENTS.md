# AGENTS.md – OpenCode Agent Operating Manual

## NUR EIN BEFEHL
```bash
cd ~/dev/stealth-runner && python3 main.py "https://heypiggy.com/?page=dashboard"
```

## WAS DER RUNNER MACHT (automatisch)
1. Browser starten (getarnt)
2. Screenshot mit nummerierten Elementen (SoM)
3. **Bild an Vision-LLM schicken** (Llama 4 Scout)
4. Vision entscheidet: welche Aktion, welches Element
5. Aktion ausführen (Klick, Type, Scroll, etc.)
6. Stealth prüfen
7. Wiederholen bis Umfrage fertig

## ABSOLUT VERBOTEN
- ❌ DOM-Prescan statt Vision – darf NIE wieder aktiviert werden
- ❌ `cua-driver`
- ❌ `open -na Chrome`
- ❌ Koordinaten raten (`--x`, `--y`)
