# Plan SR-32: Provider Auto-Detect Engine

## URL Pattern Table

```python
PROVIDER_URLS = {
    'qualtrics': [
        'eu.qualtrics.com',
        'qualtrics.com/jfe/form',
        'survey.qualtrics.com',
    ],
    'tolunastart': [
        'tolunastart.com',
        'survey.toluna.com',
    ],
    'strat7': [
        'strat7audiences.com',
    ],
    'brand_ambassador': [
        'brand-ambassador.com',
    ],
    'insights_today': [
        'insights-today.com',
    ],
    'purespectrum': [
        'screener.purespectrum.com',
    ],
    'cint': [
        's.cint.com',
        'cint.com/Survey',
    ],
    'nfield': [
        'nfieldeu-interviewing.nfieldmr.com',
        'nfieldmr.com',
    ],
    'surveys_gfk': [
        'surveys.com',
    ],
    'surveyrouter': [
        'surveyrouter.com',
    ],
    'cpx_rating': [
        'offers.cpx-research.com/rating.php',
    ],
}

def detect_provider(url):
    """Priority-based URL pattern matching."""
    url_lower = url.lower()
    for provider, patterns in PROVIDER_URLS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return provider
    return 'unknown'
```

## Redirect Handler

```python
def wait_for_final_url(tab_id, port=9999, timeout=15):
    """Wait for CPX redirect to final survey URL."""
    start = time.time()
    while time.time() - start < timeout:
        pages = json.loads(urlopen(f'http://127.0.0.1:{port}/json').read())
        for p in pages:
            if p.get('id') == tab_id:
                url = p.get('url', '')
                if 'click.cpx-research.com' in url:
                    continue  # Still redirecting
                return url
        time.sleep(1)
    return None
```

## DOM Fallback Detection

```python
DOM_SIGNATURES = {
    'qualtrics': {
        'selectors': ['.NextButton', '.QuestionText', '.ChoiceStructure'],
        'text_patterns': ['Powered by Qualtrics'],
    },
    'tolunastart': {
        'selectors': ['.cf-radio', '.cf-checkbox', '.cf-ranking-answer'],
        'text_patterns': [],
    },
    'purespectrum': {
        'selectors': ['input.alpha-numeric-input'],
        'text_patterns': ['ROBOT', 'Code in das Textfeld'],
    },
    'strat7': {
        'selectors': ['.bsbutton'],
        'text_patterns': ['Strat7'],
    },
}

def detect_by_dom(ws_url):
    """Fallback: DOM element detection when URL fails."""
    js = '''(function(){
        var out = {};
        ''' + ''.join([
            f'out["{name}"] = document.querySelector("{sig["selectors"][0]}") !== null;'
            for name, sig in DOM_SIGNATURES.items() if sig.get('selectors')
        ]) + '''
        return JSON.stringify(out);
    })()'''
    
    result = eval_js(ws_url, js)
    found = json.loads(result)
    
    for provider, _ in DOM_SIGNATURES.items():
        if found.get(provider):
            return provider
    return 'unknown'
```

## Implementation: ~1.5h
