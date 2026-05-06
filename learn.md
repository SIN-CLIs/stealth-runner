# learn.md — UNVERBRÜCHLICHE WAHRHEITEN (2026-05-06)

## 🔥 CHROME: IMMER mit Accessibility + CDP starten

```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir=/tmp/heypiggy-bot \
  'https://www.heypiggy.com/?page=dashboard'
```

**NIE OHNE diese Flags. NIE playstealth. NIE ohne --force-renderer-accessibility.**

## 🔥 GOOGLE LOGIN: cua-driver + CDP = BEIDE

- **cua-driver**: für macOS System-Dialogs (Passkey/TouchID). Braucht Accessibility.
- **CDP**: für Web-Interaktion (Formulare, Buttons, Snapshot). Braucht --remote-allow-origins=*.
- **BEIDE laufen gleichzeitig auf derselben Chrome-Instanz.**
- cua-driver daemon: `nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &`

## 🔥 NIM Nemotron 3 Omni: REASONING Model

- `max_tokens=600` (nicht 200!)
- KEIN system prompt
- Chain-of-thought user prompt: "Think step by step... Your JSON:"

## 🔥 Angular v19: JS .click() IGNORIERT

- Nur CDP `Input.dispatchMouseEvent` funktioniert (isTrusted=true)

## 🔥 Gelöschte Lügen-Dateien

- `survey/login.py`: Behauptete "already_logged_in" auf Landing-Page. GELÖSCHT.
- `playstealth launch --port X`: playstealth hat KEIN --port Flag. 

## 🔥 Working Pattern: PureSpectrum Flow

1. ROBOT textarea: `textarea.value = 'ROBOT...'` + CDP-click Nächste
2. Text captcha: base64 img → NVIDIA Vision OCR → fill input → CDP-click Nächste
3. Drag puzzle: __ngContext__ recursive → dropListRef.drop()
