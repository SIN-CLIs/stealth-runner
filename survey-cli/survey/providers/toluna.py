"""TolunaStart provider patterns.

Key patterns:
  - .cf-radio for single select (use JS .click(), NOT MouseEvent!)
  - .cf-checkbox for multi select
  - button for page advance
  - input[type=number] for numeric
  - .cf-ranking-answer for ranking questions
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
