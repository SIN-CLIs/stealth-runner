#!/usr/bin/env python3
import asyncio, subprocess, json, os, sys, time
from runner import StealthExecutor, VisionClient, StealthRunner, AuditLog

BOT_PID = int(os.environ.get("STEALTH_PID", "54971"))

def find_bot_window():
    r = subprocess.run(['cua-driver', 'call', 'list_windows'], capture_output=True, text=True, timeout=10)
    data = json.loads(r.stdout)
    windows = data.get('structuredContent', data).get('windows', [])
    for w in windows:
        title = (w.get('title') or '').lower()
        if 'heypiggy' in title and w.get('pid') != 2253:
            return w['pid'], w['window_id']
    for w in windows:
        if w.get('pid') == BOT_PID:
            return BOT_PID, w['window_id']
    chrome = [w for w in windows if w.get('app_name') == 'Google Chrome']
    if chrome:
        best = sorted(chrome, key=lambda w: -w['pid'])[0]
        return best['pid'], best['window_id']
    return BOT_PID, 0

async def main():
    print("🤖 Stealth Runner v1.0")
    pid, wid = find_bot_window()
    print(f"   Bot-Chrome: PID={pid} wid={wid}")
    if not wid:
        print("❌ Kein Bot-Chrome Fenster!")
        return

    executor = StealthExecutor(pid, wid)
    vision = VisionClient()
    audit = AuditLog()

    runner = StealthRunner(pid, wid, vision, audit)
    session = await runner.run()

    print(f"\n📊 Session: {session}")
    print(f"   Audit: {audit.get_summary()['path']}")

if __name__ == "__main__":
    asyncio.run(main())
