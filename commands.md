# commands.md - Korrekte Befehle (NUR DIESE NUTZEN)

## Chrome starten (isoliert)
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# Output: {"pid": 97228, "status": "ok"}
```

## Screenshot (VOR/NACH jedem Schritt)
```bash
skylight-cli screenshot --pid <PID> --mode som --output /tmp/schritt_vor.png
```

## Elemente finden
```bash
skylight-cli list-elements --pid <PID> | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e.get('label','').lower() in ['google login-symbol', 'weiter', 'e-mail oder telefonnummer']:
        print(f'Index={e[\"index\"]}, Label=\"{e.get(\"label\",\"\")}\"')
"
```

## Element klicken (NUR per index)
```bash
skylight-cli click --pid <PID> --element-index <N>
```

## Text eingeben (NUR per index)
```bash
skylight-cli type --pid <PID> --element-index <N> --text "wert"
```

## Screen-Erkennung (da Modell keine Bilder sieht)
```bash
screen-follow --pid <PID>
# oder
unmask-cli describe --pid <PID>
```
