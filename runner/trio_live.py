#!/usr/bin/env python3
"""
TRIO LAYER v2 – Live Human-Eye-Brain-Hand System.
- EYES: cua-driver list_windows (250ms Polling)
- BRAIN: Omni analysiert in Echtzeit
- HANDS: cua-driver click --pid --window-id --element-index
"""
from __future__ import annotations
import json, os, subprocess, time, re
from pathlib import Path
import httpx

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


def cua(tool: str, args: dict = None) -> dict:
    """cua-driver call mit JSON-Args."""
    cmd = ["cua-driver", "call", tool]
    if args:
        cmd.append(json.dumps(args))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except:
        return {}


def find_popup_windows(pid: int) -> list:
    """cua-driver list_windows → Popups erkennen."""
    data = cua("list_windows")
    popups = []
    for w in data.get("windows", []):
        if w.get("pid") == pid:
            title = w.get("title", "")
            is_on = w.get("is_on_screen", False)
            # Google OAuth Popups haben bestimmte Titel
            if "google" in title.lower() or "anmelden" in title.lower():
                popups.append(w)
    return popups


def get_popup_state(pid: int, window_id: int) -> str:
    """Nur Popup-Elemente sehen (nicht die Hauptseite)."""
    data = cua("get_window_state", {"pid": pid, "window_id": window_id})
    return data.get("tree_markdown", "")


def omni_analyze_live(tree: str, context: str = "") -> dict:
    """Omni analysiert den Accessibility-Tree LIVE."""
    prompt = f"""You are a browser automation agent. This is the accessibility tree of a Google sign-in popup.

{tree[:3000]}

Context: {context}

Analyze what's visible. What action should be taken?
Output ONLY JSON:
{{"action":"click|type|wait|done",
 "element_index":0,
 "label":"...",
 "reasoning":"..."}}"""

    try:
        r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                       json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                             "max_tokens": 200, "temperature": 0.1}, timeout=15)
        msg = r.json()["choices"][0]["message"]
        text = msg.get("reasoning") or msg.get("content") or "{}"
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group()) if m else {"action": "wait"}
    except:
        return {"action": "wait"}


def trio_live_loop(pid: int, profile_path: str = "profiles/jeremy.yaml") -> None:
    """LIVE Loop: 250ms Polling → Popup-Erkennung → Omni → Click."""
    import yaml
    profile = yaml.safe_load(Path(profile_path).read_text())
    email = profile.get("google_email", "")
    password = profile.get("google_password", "")

    print(f"🧠 TRIO LIVE LOOP: PID={pid}\n", flush=True)
    known_windows = set()
    context = "starting"
    step = 0

    while step < 50:
        step += 1
        time.sleep(0.25)  # 250ms Polling

        # 1. EYES: Neue Popups erkennen
        all_windows = cua("list_windows").get("windows", [])
        current_ids = set()
        for w in all_windows:
            if w.get("pid") == pid:
                wid = w.get("window_id", 0)
                current_ids.add(wid)
                if wid not in known_windows:
                    title = w.get("title", "")
                    print(f"\n👁 NEUES FENSTER: WindowID={wid} \"{title}\"", flush=True)
                    known_windows.add(wid)

        # 2. BRAIN: Popup analysieren + handeln
        for w in all_windows:
            if w.get("pid") != pid or not w.get("is_on_screen", False):
                continue
            title = w.get("title", "")
            wid = w.get("window_id", 0)

            if "google" in title.lower() or "anmelden" in title.lower():
                tree = get_popup_state(pid, wid)
                if not tree:
                    continue

                # Omni entscheidet
                decision = omni_analyze_live(tree, context)
                action = decision.get("action", "wait")
                idx = decision.get("element_index", 0)

                print(f"  🧠 Omni: {action} [{idx}] ({decision.get('reasoning','')[:60]})", flush=True)

                if action == "click" and idx > 0:
                    cua("click", {"pid": pid, "window_id": wid, "element_index": idx})
                    context = f"clicked {idx} on {title}"
                    time.sleep(0.5)

                elif action == "type" and idx > 0:
                    text = email if "email" in title.lower() else password
                    if text:
                        cua("set_value", {"pid": pid, "window_id": wid, "element_index": idx, "value": text})
                        context = f"typed into {idx}"
                        time.sleep(0.5)

                elif action == "done":
                    print(f"  ✅ Fertig!", flush=True)
                    return

    print(f"\n✅ TRIO LIVE LOOP beendet ({step} Schritte)", flush=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python trio_live.py <PID>")
        sys.exit(1)
    trio_live_loop(int(sys.argv[1]))
