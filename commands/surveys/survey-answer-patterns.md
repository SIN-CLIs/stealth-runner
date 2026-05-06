# Survey Answer Pattern (VERIFIED 2026-05-06)

## Radio Button
```python
# Click first radio button
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelectorAll("input[type=radio]");if(i.length>0){i[0].checked=true;i[0].dispatchEvent(new Event("change",{bubbles:true}));return "OK:"+i[0].parentElement.textContent.trim().substring(0,30);}return "NIX";})()'}}))
```

## Checkbox
```python
# Toggle first unchecked checkbox
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelectorAll("input[type=checkbox]");if(i.length>0&&!i[0].checked){i[0].click();return "CHECKED";}return "NOCHECK";})()'}}))
```

## Text Input
```python
# Set value on input by position
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inputs=document.querySelectorAll("input[type=text], input[type=number]");for(var i=0;i<inputs.length;i++){var r=inputs[i].getBoundingClientRect();if(r.top>400){inputs[i].value="10785";inputs[i].dispatchEvent(new Event("input",{bubbles:true}));inputs[i].dispatchEvent(new Event("change",{bubbles:true}));return "SET:"+inputs[i].value;}}return "NIX";})()'}}))
```

## Submit (Form)
```python
# Submit form or click next button
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var f=document.querySelector("form");if(f){f.submit();return "SUBMIT";}var b=document.querySelectorAll("button, a");for(var i=0;i<b.length;i++){var t=b[i].textContent.trim();if(t.includes("Weiter")||t.includes("Next")||t.includes("Submit")){b[i].click();return "BTN:"+t;}}return "NIX";})()'}}))
```

## Click by Text
```python
# Click element containing specific text
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("*");for(var i=0;i<all.length;i++){var t=all[i].textContent||"";if(t.trim()==="Männlich"){all[i].click();return "CLICKED";}}return "NIX";})()'}}))
```

## Qualtrics Patterns (2026-05-06)

Qualtrics surveys (`eu.qualtrics.com/jfe/form/`) use different DOM than TolunaStart:

```python
# Next button (Qualtrics-specific)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector(".NextButton").click()'}}))

# Radio button (global index)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelectorAll("input[type=radio]")[INDEX].click()'}}))

# Checkbox (multi select)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelectorAll("input[type=checkbox]")[INDEX].click()'}}))

# Textarea input (with Event dispatch)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var t=document.querySelector("textarea:not(.g-recaptcha-response)");t.value="TEXT";t.dispatchEvent(new Event("input",{bubbles:true}));t.dispatchEvent(new Event("change",{bubbles:true}));})()'}}))

# Matrix table (rows × columns)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rows=document.querySelectorAll("table.ChoiceStructure tbody tr");var ratings=[1,1,2,1,4,1,1,0];for(var i=0;i<rows.length;i++){var radios=rows[i].querySelectorAll("input[type=radio]");if(radios[ratings[i]])radios[ratings[i]].click();}})()'}}))
```

## Status
✅ VERIFIED — All patterns work on Samplicio.us, Civey, Qualtrics, and other survey providers.