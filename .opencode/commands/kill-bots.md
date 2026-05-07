---
description: Alle Bot-Chrome Prozesse sicher beenden (NUR /tmp/heypiggy-new-*)
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-flash
---
Beende ALLE Bot-Chrome Prozesse sicher:

⚠️ WARNUNG: NUR Chrome mit profile=/tmp/heypiggy-new-* beenden!
NIE user Chrome anfassen!

```bash
ps aux | grep 'Google Chrome' | grep 'heypiggy-new' | awk '{print $2}' | while read pid; do
  kill $pid 2>/dev/null && echo "Killed PID $pid"
done
echo "Done"
```

Dann Registry leeren: `rm -f ~/.stealth/sessions.json`
