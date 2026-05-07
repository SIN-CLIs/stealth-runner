"""Qualtrics provider patterns.

WARUM: Qualtrics ist der dominanteste Survey-Provider. Seine SPA-Architektur
(webpack) lädt JS asynchron — generische Clicks auf <button> schlagen fehl
weil der NextButton erst nach JS-Init existiert (.NextButton, nicht button).
Dieses Modul liefert die korrekten NEMO-Actions und Wartezeiten.

ARCHITEKTUR: Statische Command-Map (COMMANDS) + Detection-Heuristik.
Commands: click_next (.NextButton), click_radio (input[type=radio]),
fill_textarea (id=QR~...), fill_matrix (table.ChoiceStructure).
Wartezeit: 3-5s nach Seitenwechsel (JS-Ladezeit).
Completion-Marker: "zurück zur website", "gutgeschrieben", etc.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

COMPLETION_MARKERS = [
    "zurück zur website",
    "gutgeschrieben",
    "vielen dank für ihre teilnahme",
]

COMMANDS = {
    "click_next": 'document.querySelector(".NextButton").click()',
    "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox]")[{idx}].click()',
    "fill_text": '''(function(v){
        var t=document.querySelector("textarea:not(.g-recaptcha-response)");
        if(!t){var i=document.querySelector("input[type=text],input[type=number]");
        if(i){i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));
        i.dispatchEvent(new Event("change",{bubbles:true}));}}
        else{t.value=v;t.dispatchEvent(new Event("input",{bubbles:true}));
        t.dispatchEvent(new Event("change",{bubbles:true}));}
    })("{value}")''',
}


def get_action_for_question(question_text, profile):
    """Match a question to profile data.

    Returns:
        {"index": int, "value": str} or None
    """
    q = question_text.lower()

    # Gender
    if "geschlecht" in q:
        return {"index": 0}  # Männlich = first radio
    if "gender" in q or "sex" in q:
        return {"index": 1}  # Male = second radio

    # Age
    if "alter" in q or "age" in q or "old are you" in q:
        age = profile.get("age", 32)
        if age < 16: return {"index": 0}
        if age < 25: return {"index": 1}
        if age < 40: return {"index": 2}
        if age < 60: return {"index": 3}
        return {"index": 4}

    # State/Bundesland
    if "bundesland" in q or "state" in q or "wohnen" in q:
        # Berlin is usually index 2-5
        return {"index": 3}

    # Employment
    if "berufstätig" in q or "employment" in q or "erwerbstätig" in q:
        return {"index": 1}  # employed_fulltime

    # Education
    if "bildung" in q or "education" in q or "schulabschluss" in q:
        edu = profile.get("education", "abitur")
        if edu == "abitur": return {"index": 3}
        if edu == "university": return {"index": 4}
        return {"index": 2}

    # Household income
    if "einkommen" in q or "income" in q or "haushalt" in q:
        return {"index": 3}  # 3000-4000

    # Household size
    if "personen" in q or "household" in q or "haushalt" in q:
        size = profile.get("household_size", 3)
        if size < 2: return {"index": 0}
        if size == 2: return {"index": 1}
        if size == 3: return {"index": 2}
        return {"index": 3}

    return None
