# ============================================================
# survey_runner.py — HeyPiggy Survey Automation (IN DEVELOPMENT)
# ============================================================
# Baut Schritt für Schritt: commands → steps → flows → box API
#
# Phase 1: scan() — verfügbare Surveys erkennen ✅
# Phase 2: start() + prequalify() — starten + vorqualifizieren ⬅️
# Phase 3: complete() — Survey durchführen + abschließen
# Phase 4: run() — Box API (alles automatisch)
#
# Survey-Ablauf:
#   1. Umfrage anklicken
#   2. Logik: machbar? (kein Webcam/Foto → sonst ablehnen)
#   3. Vorqualifizierung (Fragen + ggf. Captcha)
#   4. Antworten in Persona speichern
#   5. Neuer Tab → richtige Umfrage
#   6. Umfrage abschließen
#   7. Tab schließen
#   8. Bewertungsfeld (0,01€ für Text)
#   9. Weiter zur nächsten
# ============================================================

import asyncio
import json
import time
import subprocess
import re
import os
import base64
import urllib.request
import websocket


# === AUDIO BOX INTEGRATION ===

def _detect_audio_question(pid):
    """Prüft ob aktuelle Seite eine Audio-Frage hat."""
    try:
        cdp_port = _find_cdp_port(pid)
        if not cdp_port: return False, {}
        
        r = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5)
        pages = json.loads(r.read())
        for p in pages:
            url = p.get('url', '')
            if any(x in url for x in ['nfieldmr.com', 'tolunastart.com', 'samplicio.us', 'cint.com']):
                ws = websocket.create_connection(p['webSocketDebuggerUrl'], timeout=5, suppress_origin=True)
                ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":"""
                    (function() {
                        var v = document.querySelector('video, audio');
                        var t = document.body ? document.body.innerText : '';
                        var hasAudioWords = /audiodatei|abspielen|hören|play|listen/i.test(t);
                        return JSON.stringify({video:!!v, audioWords:hasAudioWords, blob:v&&v.src&&v.src.startsWith('blob:')});
                    })()
                """}}))
                resp = json.loads(ws.recv())
                ws.close()
                val = json.loads(resp.get("result",{}).get("result",{}).get("value","{}"))
                if val.get('video') or val.get('audioWords'):
                    return True, val
        return False, {}
    except:
        return False, {}


def _handle_audio_question(pid, options=None):
    """
    Audio-Frage automatisch beantworten.
    Nutzt BlackHole + ffmpeg + NVIDIA Omni.
    
    Args:
        pid: Chrome PID
        options: Antwort-Optionen z.B. ["Elefant","Hahn","Hund","Katze"]
    
    Returns:
        str: Erkannte Antwort oder None
    """
    from cli.modules.audio_box import capture_and_analyze, check_pipeline
    
    # Prüfe Pipeline
    status = check_pipeline()
    if not status.get("blackhole"):
        print("  ⚠️ BlackHole nicht installiert! Überspringe Audio-Frage.")
        return None
    
    cdp_port = _find_cdp_port(pid)
    if not cdp_port:
        return None
    
    print(f"  🎤 Audio-Frage erkannt! Nehme {6}s auf...")
    result = capture_and_analyze(cdp_port, duration=6, options=options)
    
    if result.get("answer"):
        print(f"  ✅ Omni sagt: {result['answer']}")
        return result["answer"]
    
    print(f"  ❌ Keine Antwort erkannt. Omni: {result.get('content','')}")
    return None


# === PERSONA (Antwort-Profil) ===

_persona = {
    "geschlecht": "männlich",
    "alter": "42",
    "einkommen": "75000",
    "plz": "10115",
    "beruf": "Softwareentwickler",
    "bildung": "Hochschule/Universität",
    "kinder": "nein",
    "haushalt": "1 Person",
    "bundesland": "Berlin",
    "raucher": "nein",
    "haustiere": "nein",
    "fahrzeug": "ja",
    "wohnung": "Mietwohnung",
    "internet": "täglich",
    "social_media": "täglich",
    "streaming": "täglich",
    "online_shopping": "monatlich",
    "gesundheit": "gut",
}

_antwort_history = []


def _persona_antwort(frage_text):
    """Findet passende Antwort aus Persona für eine Frage."""
    frage = frage_text.lower()
    if any(w in frage for w in ["geschlecht", "gender", "sex", "mann", "frau", "divers"]):
        return _persona["geschlecht"]
    if any(w in frage for w in ["alter", "age", "jahrgang", "geboren", "jahre", "old"]):
        return _persona["alter"]
    if any(w in frage for w in ["einkommen", "income", "gehalt", "verdienst", "salary", "euro"]):
        return _persona["einkommen"]
    if any(w in frage for w in ["plz", "postleitzahl", "zip", "wohnort", "stadt"]):
        return _persona["plz"]
    if any(w in frage for w in ["beruf", "job", "arbeit", "beschäftigt", "employed", "occupation"]):
        return _persona["beruf"]
    if any(w in frage for w in ["bildung", "education", "schule", "studium", "abschluss", "ausbildung"]):
        return _persona["bildung"]
    if any(w in frage for w in ["kind", "kinder", "child", "children"]):
        return _persona["kinder"]
    if any(w in frage for w in ["haushalt", "haushaltsgröße", "household", "personen", "mitbewohner"]):
        return _persona["haushalt"]
    if any(w in frage for w in ["raucher", "smoker", "rauch"]):
        return _persona["raucher"]
    if any(w in frage for w in ["haustier", "haustiere", "pet", "tiere"]):
        return _persona["haustiere"]
    if any(w in frage for w in ["fahrzeug", "auto", "car", "vehicle", "mobil"]):
        return _persona["fahrzeug"]
    return None


# === CDP HELPER ===

async def _cdp_evaluate(cdp_port, page_id, expression):
    import websockets
    ws_url = f"ws://127.0.0.1:{cdp_port}/devtools/page/{page_id}"
    async with websockets.connect(ws_url, ping_interval=None, close_timeout=5) as ws:
        await ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expression}
        }))
        resp = json.loads(await ws.recv())
        return resp.get("result", {}).get("result", {}).get("value")


def _cdp_evaluate_sync(cdp_port, page_id, expression):
    try:
        return asyncio.run(_cdp_evaluate(cdp_port, page_id, expression))
    except:
        return None


def _get_page_id(cdp_port):
    import http.client
    try:
        conn = http.client.HTTPConnection(f"127.0.0.1:{cdp_port}")
        conn.request("GET", "/json")
        resp = conn.getresponse()
        pages = json.loads(resp.read())
        conn.close()
        for p in pages:
            if p.get("type") == "page" and "parentId" not in p:
                return p.get("id")
        return pages[0]["id"] if pages else None
    except:
        return None


def _run_skylight(*args):
    cmd = ["skylight-cli"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    out = (result.stdout or "") + (result.stderr or "")
    idx = out.find("{")
    if idx < 0:
        return {"elements": []}
    return json.loads(out[idx:])


def _find_cdp_port(pid):
    import psutil
    try:
        proc = psutil.Process(pid)
        for conn in proc.connections():
            if conn.status == "LISTEN" and conn.laddr.port > 0:
                return conn.laddr.port
    except:
        pass
    return None


# === FRAGE-ERKENNUNG via AX-TREE ===

def _detect_questions(pid):
    """
    Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.
    
    Filtert Browser-Chrome-Elemente raus (Indices < 22).
    Erkennt nur Elemente INNERHALB der AXWebArea.
    
    Returns:
        dict mit:
        - question_text: str (die Frage)
        - options: list[dict] (Antwortmöglichkeiten)
        - type: "radio" | "checkbox" | "text" | "captcha" | "none"
        - next_button: int | None (Index von Weiter/Nächst)
    """
    els = _run_skylight("list-elements", "--pid", str(pid)).get("elements", [])
    
    # Browser-Chrome-Filter: Elemente unterhalb der AXWebArea
    # AXWebArea ist typischerweise bei Index 22
    # Alles davor = Browser-Chrome (Toolbar, Tabs, Adressleiste, etc.)
    webarea_start = 22  # Erster Index nach Browser-Chrome
    
    # Frage-Texte finden (AXStaticText mit Frage-Charakter)
    questions = []
    options = []
    next_idx = None
    
    for e in els:
        lbl = e.get("label", "")
        role = e.get("role", "")
        idx = e.get("index")
        
        # Browser-Chrome-Elemente überspringen (Toolbar, Tabs)
        if idx is not None and idx < webarea_start:
            continue
        
        # Browser-Chrome-Labels erkennen und überspringen
        if lbl in ("Neuer Tab", "Tabs suchen", "Schließen-Taste", "Taste zum Minimieren",
                   "Taste „Vollbildmodus“", "Zurück", "Vorwärts", "Neu laden",
                   "Privat", "Tab in geteilter Ansicht öffnen", "Website-Informationen anzeigen",
                   "Adress- und Suchleiste", "Lesezeichen für diesen Tab erstellen",
                   "Lesezeichen\u00a0– angepinnt", "Tabgruppen", "Schließen"):
            continue
        if lbl.startswith("Du verwendest ein nicht unterstütztes"):
            continue
        
        # "Nächste" / "Weiter" / "Next" Button erkennen
        if "AXButton" in role and lbl in ("Nächste", "Weiter", "Next", "Submit", "Continue"):
            next_idx = idx
        
        # AXRadioButton = Antwortmöglichkeit
        if "AXRadioButton" in role and lbl:
            options.append({"label": lbl, "index": idx, "type": "radio"})
        
        # AXCheckBox = Mehrfachauswahl
        if "AXCheckBox" in role and lbl:
            options.append({"label": lbl, "index": idx, "type": "checkbox"})
        
        # AXTextField = Texteingabe
        if "AXTextField" in role and lbl:
            options.append({"label": lbl, "index": idx, "type": "text"})
        
        # Frage-Text (StaticText mit Frage-Wörtern)
        if "AXStaticText" in role and lbl:
            if any(w in lbl.lower() for w in ["?", "wähle", "bitte", "welche", "wie", "was", "sind sie"]):
                questions.append(lbl)
    
    # Captcha erkennen
    for e in els:
        lbl = e.get("label", "").lower()
        role = e.get("role", "")
        if "captcha" in lbl or "recaptcha" in lbl or "ich bin kein roboter" in lbl:
            return {"question_text": "CAPTCHA", "options": [], "type": "captcha", "next_button": None, "question_element": None}
    
    # Frage-Typ bestimmen
    if options:
        types = set(o["type"] for o in options)
        if "text" in types:
            qtype = "text"
        elif "checkbox" in types:
            qtype = "checkbox"
        else:
            qtype = "radio"
    else:
        qtype = "none"
    
    return {
        "question_text": questions[0] if questions else "",
        "options": options,
        "type": qtype,
        "next_button": next_idx,
        "question_element": None
    }


def _click_option(pid, option):
    """Klickt eine Antwortmöglichkeit (RadioButton/CheckBox)."""
    _run_skylight("click", "--pid", str(pid), "--element-index", str(option["index"]))


def _answer_text(pid, textfield, answer):
    """Tippt eine Antwort in ein Textfeld."""
    _run_skylight("click", "--pid", str(pid), "--element-index", str(textfield["index"]))
    time.sleep(0.3)
    _run_skylight("type", "--pid", str(pid), "--element-index", str(textfield["index"]), "--text", answer)


def _click_next(pid, next_idx):
    """Klickt den Weiter/Nächst-Button."""
    if next_idx is not None:
        _run_skylight("click", "--pid", str(pid), "--element-index", str(next_idx))
        return True
    return False


# === LOGIK-ENTSCHEIDUNG via Vision Gate ===

def _check_feasible_vision(pid, screenshot_path):
    """
    Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).
    
    Erkennt: Registrierungspflicht, Webcam/Foto, Captcha, etc.
    Wird VOR "Umfrage starten" Klick aufgerufen.
    """
    from cli.modules import logic_module
    return logic_module.check_feasibility(pid, screenshot_path)


def _take_screenshot(pid, output_path="/tmp/survey_check.png"):
    """Macht einen Screenshot und speichert ihn."""
    import subprocess
    subprocess.run(["skylight-cli", "screenshot", "--pid", str(pid), "--mode", "som"],
                   capture_output=True, timeout=10)
    subprocess.run(["cp", "skylight_screenshot.png", output_path],
                   capture_output=True)
    return output_path


# === FRAGE BEANTWORTEN ===

def _answer_question(pid, question_info):
    """
    Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.
    
    - radio: erste passende Option wählen (Ja bevorzugt)
    - checkbox: erste Option
    - text: Persona-Antwort
    """
    qtype = question_info["type"]
    qtext = question_info["question_text"]
    options = question_info["options"]
    next_idx = question_info["next_button"]
    
    answered = False
    
    if qtype == "radio":
        # AXRadioButton: eine Option auswählen
        # "Ja" bevorzugen, sonst erste passende Persona-Antwort
        ja_opt = None
        persona_opt = None
        first_opt = None
        
        for o in options:
            if first_opt is None:
                first_opt = o
            lbl_lower = o["label"].lower()
            if lbl_lower in ("ja", "yes", "stimme zu", "trifft zu", "zutreffend", "agree"):
                ja_opt = o
                break
            if lbl_lower in ("nein", "no", "trifft nicht zu", "disagree"):
                if ja_opt is None:
                    ja_opt = None  # keep looking for "Ja"
            # Persona-Matching
            persona_ans = _persona_antwort(qtext)
            if persona_ans and persona_ans.lower() in lbl_lower:
                persona_opt = o
        
        chosen = ja_opt or persona_opt or first_opt
        if chosen:
            _click_option(pid, chosen)
            _antwort_history.append({"frage": qtext, "antwort": chosen["label"]})
            answered = True
    
    elif qtype == "text":
        # AXTextField: Text eingeben
        persona_ans = _persona_antwort(qtext) or "keine Angabe"
        if options:
            _answer_text(pid, options[0], persona_ans)
            _antwort_history.append({"frage": qtext, "antwort": persona_ans})
            answered = True
    
    elif qtype == "checkbox":
        # AXCheckBox: erste Option
        if options:
            _click_option(pid, options[0])
            _antwort_history.append({"frage": qtext, "antwort": options[0]["label"]})
            answered = True
    
    # Weiter klicken
    if answered and next_idx is not None:
        _click_next(pid, next_idx)
    
    return answered


# === PHASE 1: SURVEY SCAN ===

def scan_surveys(pid):
    """
    Scannt verfügbare Surveys via CDP DOM.
    
    Returns:
        list[dict]: [{id, payout, time}] oder None
    """
    cdp_port = _find_cdp_port(pid)
    page_id = _get_page_id(cdp_port) if cdp_port else None
    if not cdp_port or not page_id:
        return None
    
    js = """
(function() {
    let surveys = [];
    let items = document.querySelectorAll('.survey-item, [id^="survey-"]');
    items.forEach(el => {
        let onclick = el.getAttribute('onclick') || '';
        let m = onclick.match(/clickSurvey\\(['"](\\d+)['"]\\)/);
        let id = m ? m[1] : (el.id ? el.id.replace('survey-', '') : '');
        if (!id) return;
        let payout_text = (el.querySelector('.survey-item-payout') || el).textContent.trim();
        let payout = parseFloat(payout_text.replace('€', '').replace(',', '.').trim()) || 0;
        let time_text = (el.querySelector('.survey-item-time') || el).textContent.trim();
        let time_min = parseInt(time_text) || 0;
        surveys.push({id: id, payout: payout, time: time_min});
    });
    return JSON.stringify(surveys);
})()
    """
    result = _cdp_evaluate_sync(cdp_port, page_id, js)
    try:
        surveys = json.loads(result) if result else []
    except:
        surveys = []
    surveys.sort(key=lambda s: s.get("payout", 0), reverse=True)
    return surveys


# === PHASE 2: SURVEY START + PRE-QUALIFICATION ===

def start_survey(pid, survey_id):
    """
    Startet einen Survey per CDP Click.
    
    Returns:
        dict: {"success": bool, "survey_id": str, "popup_detected": bool}
    """
    cdp_port = _find_cdp_port(pid)
    page_id = _get_page_id(cdp_port) if cdp_port else None
    if not cdp_port or not page_id:
        return {"success": False, "survey_id": survey_id, "popup_detected": False, "error": "CDP nicht verfügbar"}
    
    js = f"""
(function() {{
    let el = document.getElementById('survey-{survey_id}');
    if (!el) {{ el = document.querySelector('[data-survey="{survey_id}"], .survey-item'); }}
    if (el && el.onclick) {{ el.click(); return 'clicked_via_onclick'; }}
    else if (el) {{ el.click(); return 'clicked_via_dom'; }}
    return 'not_found';
}})()
    """
    result = _cdp_evaluate_sync(cdp_port, page_id, js)
    clicked = result and "clicked" in result
    
    return {
        "success": clicked,
        "survey_id": survey_id,
        "popup_detected": False,
        "error": None if clicked else f"Survey {survey_id} nicht klickbar"
    }


def prequalify(pid):
    """
    Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.
    
    1. Cookie-Modal-Logik: detect → accept → verify (atomar!)
    2. Screenshot + Vision Check (NVIDIA + Pixtral)
    3. Erkennt Registrierung, Captcha, Webcam, etc.
    4. Wenn machbar: Fragen automatisch beantworten
    5. Wenn nicht: skip mit Begründung
    
    Returns:
        dict: {"success": bool, "questions_answered": int, "feasible": bool,
               "message": str, "history": list}
    """
    global _antwort_history
    _antwort_history = []
    
    # ─── AUDIO-FRAGE: Automatisch erkennen + beantworten ────────
    has_audio, audio_info = _detect_audio_question(pid)
    if has_audio:
        print(f"  🔊 Audio-Frage erkannt! Starte Audio-Box...")
        # Extrahiere Optionen aus dem Text
        options = ["Elefant", "Hahn", "Hund", "Katze"]  # Default
        # Versuche Optionen aus AX-Tree zu extrahieren
        try:
            from cli.modules import skylight_main
            els = skylight_main.list_elements(pid)
            found = []
            for e in els:
                lbl = e.get("label", "")
                if lbl in options:
                    found.append(lbl)
            if found:
                options = found
        except:
            pass
        
        answer = _handle_audio_question(pid, options=options)
        if answer:
            print(f"  ✅ Audio beantwortet: {answer}")
            _antwort_history.append({"frage": "Audio-Frage", "antwort": answer})
            questions_answered += 1
            time.sleep(2)
            # Weiter klicken
            from cli.modules import skylight_main
            skylight_main.scan_and_click(pid, "Weiter")
    
    # ─── COOKIE-MODAL: Vor jeder Umfrage erkennen + klicken ──────
    from cli.modules import cookie_modal
    cookie_modal.handle(pid)
    time.sleep(1)
    
    # VISION CHECK: Vor der Vorqualifizierung per Screenshot prüfen
    try:
        screenshot = _take_screenshot(pid)
        vision_check = _check_feasible_vision(pid, screenshot)
        
        if not vision_check.get("feasible", True):
            return {
                "success": False,
                "questions_answered": 0,
                "feasible": False,
                "message": f"Vision-Check: {vision_check.get('reason', 'Nicht machbar')}",
                "history": _antwort_history
            }
    except Exception as e:
        # Vision-Check fehlgeschlagen -> AX-basiert weitermachen
        pass
    
    max_questions = 20
    questions_answered = 0
    
    for round_num in range(max_questions):
        q = _detect_questions(pid)
        
        if q["type"] == "none" and questions_answered > 0:
            return {
                "success": True,
                "questions_answered": questions_answered,
                "feasible": True,
                "message": "Alle Fragen beantwortet",
                "history": _antwort_history
            }
        
        if q["type"] == "captcha":
            # Captcha automatisch lösen via stealth-captcha Module
            from stealth_captcha.captcha_handler import handle_captcha_in_survey
            
            captcha_ok = handle_captcha_in_survey(pid, current_url or "")
            
            if captcha_ok:
                questions_answered += 1
                time.sleep(3)
                continue  # Nach Captcha weiter zur nächsten Frage
            
            return {
                "success": False,
                "questions_answered": questions_answered,
                "feasible": False,
                "message": f"Captcha nicht lesbar",
                "history": _antwort_history
            }
        
        if q["type"] == "none" and questions_answered == 0:
            time.sleep(1)
            continue
        
        # AX-basierte Machbarkeit
        feasible = True
        for o in q["options"]:
            ol = o["label"].lower()
            if any(w in ol for w in ["webcam", "kamera", "foto", "photo", "video", "mikrofon"]):
                feasible = False
                reason = "Webcam/Foto/Video erforderlich"
                break
        if not feasible:
            return {
                "success": False,
                "questions_answered": questions_answered,
                "feasible": False,
                "message": reason,
                "history": _antwort_history
            }
        
        if _answer_question(pid, q):
            questions_answered += 1
            time.sleep(1)
        else:
            if questions_answered > 0:
                return {
                    "success": True,
                    "questions_answered": questions_answered,
                    "feasible": True,
                    "message": f"{questions_answered} Fragen beantwortet",
                    "history": _antwort_history
                }
            return {
                "success": False,
                "questions_answered": 0,
                "feasible": False,
                "message": "Keine Antwort möglich",
                "history": _antwort_history
            }
    
    return {
        "success": True,
        "questions_answered": questions_answered,
        "feasible": True,
        "message": f"{questions_answered} Fragen (max erreicht)",
        "history": _antwort_history
    }


# === PHASE 3: SURVEY IM NEUEN TAB BEARBEITEN ===

def complete_survey(pid, timeout_minutes=15):
    """
    Bearbeitet einen Survey im neuen Tab.
    
    1. Erkennt neuen Tab (Cint, PureSpectrum, etc.)
    2. Cookie-Modal-Logik: detect → accept → verify
       NEU: atomares cookie_modal Modul mit Vision-Gate + CDP+AX
    3. Fragen erkennen + beantworten (via AX/Vision)
    4. "Weiter/Next" durchklicken
    5. Fertig-Seite erkennen + Tab schließen
    
    Returns:
        dict: {"success": bool, "questions_answered": int, "tab_closed": bool}
    """
    from cua_touch import CuATouch
    from cli.modules import cookie_modal  # <-- NEU: Atomare Cookie-Logik
    cua = CuATouch()
    
    start_time = time.time()
    questions_answered = 0
    tab_closed = False
    max_duration = timeout_minutes * 60
    
    # Warte auf neuen Tab
    time.sleep(3)
    cdp_port = _find_cdp_port(pid)
    page_id = _get_page_id(cdp_port) if cdp_port else None
    
    # ─── COOKIE-MODAL: detect → accept → verify ──────────
    # Direkt nach Tab-Wechsel: Cookie-Modal erkennen und behandeln.
    # cookie_modal.handle() macht: Screenshot → Vision → Klick → Verify.
    # Atomar, kein Monolith — Vision sagt WAS zu klicken ist,
    # CDP+AX Trinity klickt es (kein Index, deterministisch).
    cookie_handled = cookie_modal.handle(pid)
    
    for round_num in range(200):
        if time.time() - start_time > max_duration:
            break
        
        # Prüfe ob neuer Tab geöffnet wurde
        if cdp_port and page_id:
            import asyncio
            async def check_tabs():
                import websockets
                ws_url = f"ws://127.0.0.1:{cdp_port}/devtools/page/{page_id}"
                async with websockets.connect(ws_url, ping_interval=None, close_timeout=5) as ws:
                    await ws.send(json.dumps(
                        {"id": 1, "method": "Target.getTargets"}))
                    resp = json.loads(await ws.recv())
                    return resp.get("result", {}).get("targetInfos", [])
            try:
                targets = asyncio.run(check_tabs())
                survey_targets = [t for t in targets 
                                  if t.get("url") and "heypiggy" not in t.get("url","").lower()
                                  and t.get("type") == "page"]
                if survey_targets:
                    page_id = survey_targets[0]["id"]
            except:
                pass
        
        # Fragen im aktuellen Tab erkennen
        q = _detect_questions(pid)
        
        if q["type"] == "none":
            # Keine Frage -> vielleicht fertig?
            if questions_answered > 0:
                time.sleep(2)
                q2 = _detect_questions(pid)
                if q2["type"] == "none":
                    tab_closed = True
                    break
            time.sleep(1)
            continue
        
        # Frage beantworten
        if _answer_question(pid, q):
            questions_answered += 1
            time.sleep(1)
        else:
            time.sleep(1)
    
    return {
        "success": questions_answered > 0,
        "questions_answered": questions_answered,
        "tab_closed": tab_closed
    }


def close_survey_tab(pid):
    """Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück."""
    import http.client
    cdp_port = _find_cdp_port(pid)
    if cdp_port:
        conn = http.client.HTTPConnection(f"127.0.0.1:{cdp_port}")
        conn.request("GET", "/json")
        resp = conn.getresponse()
        pages = json.loads(resp.read())
        conn.close()
        for p in pages:
            url = p.get("url", "")
            if url and "heypiggy" not in url.lower() and p.get("type") == "page":
                ws_url = p.get("webSocketDebuggerUrl", "")
                if ws_url:
                    import asyncio
                    async def close_tab():
                        import websockets
                        async with websockets.connect(ws_url, ping_interval=None, close_timeout=5) as ws:
                            await ws.send(json.dumps({"id": 1, "method": "Page.close"}))
                            await ws.recv()
                    try:
                        asyncio.run(close_tab())
                        return True
                    except:
                        pass
    return False


def handle_review(pid):
    """
    Bearbeitet das Bewertungsfeld nach dem Survey.
    
    Schreibt kurzen Text + reicht ein (0,01€).
    """
    els = _run_skylight("list-elements", "--pid", str(pid)).get("elements", [])
    
    # Textfeld finden
    text_idx = None
    submit_idx = None
    for e in els:
        lbl = e.get("label", "")
        role = e.get("role", "")
        idx = e.get("index")
        if idx and idx >= 22:
            if "AXTextField" in role and lbl:
                if text_idx is None:
                    text_idx = idx
            if "AXButton" in role and any(x in lbl for x in ["einreichen", "submit", "senden", "abschicken", "bewerten"]):
                submit_idx = idx
    
    if text_idx:
        _run_skylight("click", "--pid", str(pid), "--element-index", str(text_idx))
        time.sleep(0.3)
        _run_skylight("type", "--pid", str(pid), "--element-index", str(text_idx),
                       "--text", "Interessante Umfrage, gerne wieder!")
        time.sleep(0.5)
        if submit_idx:
            _run_skylight("click", "--pid", str(pid), "--element-index", str(submit_idx))
            time.sleep(2)
            return True
    return False


def check_balance(pid):
    """Prüft ob sich das Guthaben erhöht hat."""
    els = _run_skylight("list-elements", "--pid", str(pid)).get("elements", [])
    for e in els:
        lbl = e.get("label", "")
        if "money bag" in lbl:
            return lbl
    return None


# === PHASE 4: BOX API ===

def run(pid, max_surveys=10):
    """
    PUBLIC BOX API: Komplette Survey Automation.
    
    Führt Surveys nacheinander aus:
    1. Scan verfügbare Surveys
    2. Starte besten Survey
    3. Vision-Logik-Check (machbar?)
    4. Vorqualifizierung beantworten
    5. "Umfrage starten" klicken
    6. Survey im Tab bearbeiten
    7. Tab schließen
    8. Bewertungsfeld (0,01€)
    9. Balance prüfen → Nächster Survey
    
    Parameter:
        pid: Chrome-PID
        max_surveys: max Anzahl (default 10)
    
    Rückgabe:
        dict: {"success": bool, "surveys_completed": int,
               "earnings": str, "results": list}
    """
    results = []
    surveys_completed = 0
    
    for survey_num in range(max_surveys):
        # 1. Scan
        surveys = scan_surveys(pid)
        if not surveys:
            results.append({"step": "scan", "success": False, "error": "Keine Surveys"})
            break
        
        best = surveys[0]
        result = {"survey_id": best["id"], "payout": best["payout"]}
        
        # 2. Start
        sr = start_survey(pid, best["id"])
        result["start"] = sr["success"]
        if not sr["success"]:
            results.append(result)
            continue
        time.sleep(2)
        
        # 3. Vision-Logik-Check + Vorqualifizierung
        pq = prequalify(pid)
        result["prequalify"] = pq.get("success", False)
        result["feasible"] = pq.get("feasible", True)
        
        if not pq.get("feasible", True):
            results.append(result)
            continue
        
        time.sleep(2)
        
        # 4. "Umfrage starten" Button klicken
        els = _run_skylight("list-elements", "--pid", str(pid)).get("elements", [])
        start_btn = None
        for e in els:
            lbl = e.get("label", "")
            role = e.get("role", "")
            idx = e.get("index")
            if idx and idx >= 22 and "AXButton" in role and "starten" in lbl.lower():
                start_btn = idx
                break
        
        if start_btn:
            _run_skylight("click", "--pid", str(pid), "--element-index", str(start_btn))
            result["survey_started"] = True
            time.sleep(4)
            
            # 5. Neue Tabs erkennen
            before_tabs = _get_page_id(_find_cdp_port(pid))
            
            # 6. Survey im Tab bearbeiten
            comp = complete_survey(pid)
            result["completed"] = comp.get("success", False)
            result["questions_answered"] = comp.get("questions_answered", 0)
            
            # 7. Tab schließen
            if close_survey_tab(pid):
                result["tab_closed"] = True
                time.sleep(3)
            
            # 8. Bewertungsfeld
            if handle_review(pid):
                result["review_done"] = True
                time.sleep(2)
            
            surveys_completed += 1
        else:
            result["survey_started"] = False
            result["error"] = "Kein 'Umfrage starten' Button"
        
        # 9. Balance prüfen
        balance = check_balance(pid)
        result["balance"] = balance
        
        results.append(result)
        
        if surveys_completed >= max_surveys:
            break
    
    return {
        "success": surveys_completed > 0,
        "surveys_completed": surveys_completed,
        "earnings": sum(r.get("payout", 0) for r in results if r.get("completed")),
        "results": results
    }


def scan(pid):
    """Public API: Verfügbare Surveys scannen."""
    return scan_surveys(pid)


def start(pid, survey_id=None):
    """
    Public API: Besten oder bestimmten Survey starten.
    """
    if survey_id is None:
        surveys = scan_surveys(pid)
        if not surveys:
            return {"success": False, "survey_id": None, "error": "Keine Surveys"}
        survey_id = surveys[0]["id"]
    return start_survey(pid, survey_id)


def do_prequalify(pid):
    """Public API: Vorqualifizierung durchführen."""
    return prequalify(pid)


# === CLI TEST ===

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pid = int(sys.argv[1])
        # Step 1: Scan
        surveys = scan_surveys(pid)
        if surveys:
            best = surveys[0]
            print(f"✅ {len(surveys)} Surveys. Beste: ID={best['id']} {best['payout']}€ {best['time']}min")
            
            # Step 2: Start
            result = start_survey(pid, best['id'])
            print(f"Start: {json.dumps(result, ensure_ascii=False)}")
            
            if result["success"]:
                time.sleep(2)
                
                # Step 3: Pre-qualification
                pq = prequalify(pid)
                print(f"Prequal: {json.dumps(pq, ensure_ascii=False)}")
        else:
            print("❌ Keine Surveys gefunden")
    else:
        print(f"Usage: python3 -m cli.modules.survey_runner <PID>")
