"""TolunaStart provider patterns.

WARUM: Toluna nutzt Angular-basierte Custom-Form-Controls (.cf-radio,
.cf-checkbox). JS .click() funktioniert hier, MouseEvent/Dispatch NICHT
(Zone.js ignoriert synthetische Events). Falsche Methode → keine Selektion.
Dieses Modul liefert die korrekten NEMO-Actions für Toluna.

ARCHITEKTUR: Statische Command-Map (COMMANDS) + Detection-Heuristik.
Commands: click_radio (cf-radio), click_checkbox (cf-checkbox),
click_next (button), fill_number (input[type=number]),
fill_ranking (cf-ranking-answer).
Completion-Marker: "zurück zur website", "vielen dank", etc.

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
    "zurück zur website", "vielen dank", "survey beendet",
    "ihre meinung wurde aufgezeichnet",
]

COMMANDS = {
    "click_next": 'document.querySelector("button").click()',
    "click_element": '''(function(){
        var el=document.querySelectorAll(".cf-radio,.cf-checkbox");
        if(el[{idx}]) el[{idx}].click();
    })()''',
    "fill_text": '''(function(v){
        var i=document.querySelector("input[type=number],input[type=text]");
        if(i){i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));
        i.dispatchEvent(new Event("change",{bubbles:true}));}
    })("{value}")''',
}
