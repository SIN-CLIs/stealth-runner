# Plan SR-30: Dashboard Poller + Auto-Loop

## Overview
Automate the dashboard → API check → survey run loop. Remove manual intervention between surveys.

## Architecture

```
DashboardPoller
├── scan_ids(dashboard_ws)        → List[str] from onclick attributes
├── filter_via_api(ids)           → API check: okay / question / not_okay
├── filter_blocked_providers(ids) → Skip PureSpectrum, surveyrouter
├── prioritize(ids)               → Sort by reward estimate
└── run_loop(config)              → poll → filter → run → repeat

SurveyRunner
├── run_survey(survey_id)         → CDP flow (from SR-28)
├── rate_survey(tab_id)           → +0.01€ bonus
└── track_earnings(delta)         → JSONL log
```

## Dashboard Scan

```python
def scan_ids(dashboard_ws_url):
    """Extract survey IDs from dashboard DOM."""
    js = '''(function(){
        var out = [];
        document.querySelectorAll("[onclick*=clickSurvey]").forEach(function(c){
            var m = c.getAttribute("onclick").match(/\d+/);
            if(m) out.push(m[0]);
        });
        return out.join("|");
    })()'''
    eval(dashboard_ws_url, js) → "66845383|66845098|..."
    return ids.split('|')
```

## API Filter

```python
DETAILS_URL = "https://live-api.cpx-research.com/api/get-survey-details.php" + \
  "?output_method=jsscriptv1&app_id=11644&ext_user_id=2525530" + \
  "&secure_hash=ae75b0feca27c0f8eb356d7117d978ec" + \
  "&email=zukunftsorientierte.energie@gmail.com" + \
  "&extra_info_1=offerwall&main_info=true" + \
  "&extra_info_3=EUR&extra_info_4=nomobile"

def check_type(survey_id):
    resp = urlopen(DETAILS_URL + "&survey_id=" + survey_id)
    data = json.loads(resp.read())
    return {
        'id': survey_id,
        'type': data.get('type'),         # okay | question | not_okay
        'href': data.get('href', ''),     # redirect URL
        'provider': extract_provider(data.get('href', '')),
        'reward': data.get('reward', 0),
    }
```

## Blocked Provider Filter

```python
BLOCKED_PROVIDER_PATTERNS = [
    'screener.purespectrum.com',
    'surveyrouter.com',
]

def is_blocked(href):
    return any(p in href for p in BLOCKED_PROVIDER_PATTERNS)

def filter_surveys(ids):
    results = []
    for sid in ids:
        info = check_type(sid)
        if info['type'] != 'okay':
            continue
        if info['type'] == 'okay' and not is_blocked(info.get('href', '')):
            results.append(info)
        elif info['type'] == 'question':
            # Pre-qualifier — can still try
            results.append(info)
    return sorted(results, key=lambda x: x.get('reward', 0), reverse=True)
```

## Auto-Loop Engine

```python
class DashboardPoller:
    def __init__(self, dashboard_ws_url, cdpport=9999):
        self.dashboard_ws = dashboard_ws_url
        self.cdp = SurveyCDP(port=cdpport)
        self.balance = 0.0
        self.processed_ids = set()
    
    def poll_and_run(self, max_surveys=10, balance_target=5.0):
        balance_before = self.cdp.read_balance(self.dashboard_ws)
        
        for round_num in range(max_surveys):
            # 1. Scan dashboard
            ids = scan_ids(self.dashboard_ws)
            
            # 2. Filter
            surveys = filter_surveys(ids)
            new = [s for s in surveys if s['id'] not in self.processed_ids]
            
            if not new:
                print("🔄 Keine neuen Surveys — warte 30s...")
                time.sleep(30)
                continue
            
            # 3. Run best survey
            best = new[0]
            print(f"▶️  Starte Survey {best['id']} ({best.get('provider','?')})")
            
            result = self.cdp.run_survey(best['id'], best['href'])
            self.processed_ids.add(best['id'])
            
            if result['status'] == 'ok':
                self.track_earnings(result['earned'])
                print(f"💰 +{result['earned']}€ | Balance: {self.balance}€")
            
            # 4. Check stop conditions
            if self.balance >= balance_target:
                print(f"🎯 Balance-Ziel erreicht: {self.balance}€")
                break
            
            time.sleep(5)  # Short cooldown
```

## Implementation
| Step | Time |
|------|------|
| ID Extractor | 30min |
| API Filter | 30min |
| Provider Filter | 30min |
| Auto-Loop Engine | 1h |
| Balance Tracker | 30min |
| Integration Test | 30min |
| **Total** | **~3.5h** |
