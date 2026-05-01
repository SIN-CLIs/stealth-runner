#!/usr/bin/env python3
"""
Trio Layer – screen-follow + Omni Vision + skylight-cli.
Erkennt Popups, Fenster und klickt NUR im korrekten Kontext.
"""
from __future__ import annotations
import base64, json, os, subprocess, sys, time
from pathlib import Path

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


def capture_screen(pid: int) -> str:
    """screen-follow Screenshot → Base64 für Omni."""
    # skylight-cli screenshot (da screen-follow --video im Hintergrund)
    subprocess.run(["skylight-cli", "screenshot", "--pid", str(pid), "--mode", "som", "--output", "/tmp/trio_frame.png"],
                   capture_output=True, timeout=15)
    # Workaround: skylight schreibt ins CWD
    cwd = Path("skylight_screenshot.png")
    target = Path("/tmp/trio_frame.png")
    if cwd.exists():
        import shutil
        shutil.copy2(str(cwd), str(target))
        cwd.unlink()
    if target.exists():
        return base64.b64encode(target.read_bytes()).decode()
    return ""


def omni_analyze(b64: str, context: str = "") -> dict:
    """Omni analysiert den Screen und sagt was zu tun ist."""
    import httpx
    prompt = f"""You are a browser automation agent. Analyze this screenshot.

Context: {context}

Identify:
1. What page/window is visible? (heypiggy, google_oauth, dashboard, survey, captcha)
2. Is there a popup/overlay? What type?
3. What action should be taken next? (click, type, wait, done)
4. WHICH ELEMENT EXACTLY? Describe the label, position, and window.

Output ONLY valid JSON:
{{"window":"heypiggy|google_oauth|dashboard|survey|captcha|unknown",
 "popup":true|false,
 "popup_type":"google_signin|google_confirm|captcha|none",
 "action":"click|type|scroll|wait|done",
 "element_label":"...",
 "element_index":0,
 "reasoning":"..."}}"""

    try:
        r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                       json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": [
                           {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                           {"type": "text", "text": prompt}]}],
                             "max_tokens": 300, "temperature": 0.1},
                       timeout=30)
        msg = r.json()["choices"][0]["message"]
        text = msg.get("reasoning") or msg.get("content") or "{}"
        # JSON extrahieren
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group()) if m else {"action": "wait"}
    except Exception as e:
        return {"action": "wait", "reasoning": str(e)}


def click_element(pid: int, element_index: int) -> dict:
    """skylight-cli click – NUR mit element-index."""
    r = subprocess.run(["skylight-cli", "click", "--pid", str(pid), "--element-index", str(element_index)],
                      capture_output=True, text=True, timeout=10)
    try:
        return json.loads(r.stdout)
    except:
        return {"status": "error", "raw": r.stdout[:200]}


def type_text(pid: int, element_index: int, text: str) -> dict:
    """skylight-cli type – NUR mit element-index."""
    r = subprocess.run(["skylight-cli", "type", "--pid", str(pid), "--element-index", str(element_index), "--text", text],
                      capture_output=True, text=True, timeout=10)
    try:
        return json.loads(r.stdout)
    except:
        return {"status": "error", "raw": r.stdout[:200]}


def run_trio(pid: int, steps: int = 20, profile: str = "profiles/jeremy.yaml") -> dict:
    """Trio Layer: screen-follow → Omni → skylight-cli."""
    import yaml
    profile_data = yaml.safe_load(Path(profile).read_text())
    email = profile_data.get("google_email", "")
    password = profile_data.get("google_password", "")

    print(f"🧠 TRIO LAYER: PID={pid}\n", flush=True)
    context = "Starting Heypiggy.com login page"

    for step in range(steps):
        print(f"\n⏱ Step {step+1}/{steps}", flush=True)

        # 1. SENSE: Capture Screen
        b64 = capture_screen(pid)
        if not b64:
            print("  ❌ Kein Screenshot", flush=True)
            time.sleep(2)
            continue

        # 2. THINK: Omni analysiert
        analysis = omni_analyze(b64, context)
        action = analysis.get("action", "wait")
        label = analysis.get("element_label", "")
        idx = analysis.get("element_index", 0)
        window = analysis.get("window", "unknown")
        popup = analysis.get("popup", False)
        popup_type = analysis.get("popup_type", "none")

        print(f"  👁 Omni: {window}{' ['+popup_type+']' if popup else ''} → {action} [{idx}] '{label}'", flush=True)

        if action == "done":
            print("  ✅ Omni sagt: Fertig!", flush=True)
            break

        if action == "wait":
            time.sleep(2)
            continue

        # 3. ACT: skylight-cli ausführen
        if action == "click" and idx > 0:
            result = click_element(pid, idx)
            print(f"  🖱 Klick [{idx}]: {result.get('status', 'ok')}", flush=True)
            context = f"Clicked {label} on {window}"
        elif action == "type" and idx > 0:
            text_to_type = email if "email" in label.lower() else password if "passwort" in label.lower() else label
            result = type_text(pid, idx, text_to_type)
            print(f"  ⌨ Type [{idx}]: {result.get('status', 'ok')}", flush=True)
            context = f"Typed into {label} on {window}"
        else:
            print(f"  ⏳ Keine Aktion (idx={idx})", flush=True)
            time.sleep(2)

        time.sleep(1)

    print(f"\n✅ TRIO LAYER beendet nach {step+1} Schritten", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trio_layer.py <PID>")
        sys.exit(1)
    run_trio(int(sys.argv[1]))
