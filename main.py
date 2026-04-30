#!/usr/bin/env python3
import asyncio, subprocess, json, os, sys, time

BOT_USER_DATA = "/tmp/heypiggy-bot"

def find_bot_pid():
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", f"user-data-dir={BOT_USER_DATA}"], text=True
        ).strip()
        pids = [int(p) for p in out.split("\n") if p]
        return min(pids) if pids else 0
    except:
        return 0

async def main():
    pid = find_bot_pid()
    if not pid:
        print("❌ Bot-Chrome nicht gefunden. Starte mit:")
        print("   playstealth-cli launch --url 'https://heypiggy.com/?page=dashboard' --json")
        return

    from runner import StealthExecutor, VisionClient, AuditLog
    from runner.state_machine import StealthRunner

    wid = 0
    e = StealthExecutor(pid, wid)
    v = VisionClient()
    a = AuditLog()

    print(f"🤖 StealthRunner — PID={pid} | backend={e.backend}")
    runner = StealthRunner(pid, wid, v, a)
    session = await runner.run()
    print(f"💰 EUR: {session.get('earnings_eur',0):.2f} | Steps: {session.get('steps',0)} | Rec: {session.get('recoveries',0)}")

if __name__ == "__main__":
    asyncio.run(main())
