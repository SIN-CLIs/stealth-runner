# Plan 05: Provider Reliability

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 1-4  
> **Priority**: P0

## Ziel

Provider-Verhalten wird lokal, testbar und austauschbar. Qualtrics, Toluna, Strat7 und PureSpectrum bekommen echte Adapter statt verstreuter Selektor-Hacks.

## Problem

Aktuell ist Provider-Wissen verteilt ueber:

- `survey-cli/survey/execute.py`
- `survey-cli/survey/runner.py`
- `survey-cli/survey/snapshot.py`
- `survey-cli/survey/providers/*.py`
- `survey-cli/tools/tool_*.py`

Das verletzt Locality. Ein Qualtrics-Fix kann mehrere Dateien brauchen und trotzdem live den falschen Tab treffen.

## ProviderAdapter Interface

```python
class ProviderAdapter(Protocol):
    name: str

    def matches(self, url: str, text: str, snapshot: CompactSnapshot) -> bool:
        """Return True if this adapter owns the current page."""

    def plan_actions(self, snapshot: CompactSnapshot, persona: Persona) -> list[Action]:
        """Return semantic actions for this provider."""

    def execute_action(self, action: Action, cdp: CDPConnection) -> ActionResult:
        """Execute one action using provider-correct DOM/CDP behavior."""

    def detect_completion(self, text: str, url: str, snapshot: CompactSnapshot) -> CompletionState:
        """Return incomplete, completed, screen_out, blocked, or error."""
```

## Adapter Prioritaet

| Provider | Prio | Warum | Kernthema |
|---|---|---|---|
| Qualtrics | P0 | blockiert konkrete Payouts | `.NextButton`, `.LabelWrapper`, language page |
| Generic completion | P0 | Erfolg darf nicht uebersehen werden | thank-you, redirects, modal close |
| TolunaStart | P1 | bekannter Provider | `.cf-radio`, hidden forms |
| Strat7 | P1 | einfacher Reward-Provider | `.bsbutton`, radio |
| PureSpectrum | P1 | viele IDs, CAPTCHA/Angular | trusted CDP events, captcha boundary |
| CloudResearch | P2 | React role buttons | `[role=button]`, native setter |

## Qualtrics P0 Fix

Aktuelle Issues:

- Language page stuck.
- `.NextButton` wird nicht erkannt.
- Leaf-node Scan ist zu aggressiv.

Plan:

1. Snapshot scannt interaktive Container, nicht nur Text-Leaves.
2. QualtricsAdapter kennt `.LabelWrapper`, `.ChoiceStructure`, `.NextButton`.
3. Auswahl wird verifiziert: checked/aria-selected/class state oder DOM hash changed.
4. Next wird explizit nach Auswahl gedrueckt.
5. Anti-stuck hash bricht nach N identischen States ab und wechselt Strategy.

## New-tab vs In-page

ProviderAdapter entscheidet nicht allein ueber Tab-Lifecycle. Das gehoert zu `SurveyOpener`/`TabManager`:

- Vor clickSurvey: Tabs snapshot.
- Nach clickSurvey: Tabs vergleichen.
- New tab: aktive Survey-WS umschalten.
- In-page: Dashboard-WS behalten und Modal root scannen.

## DOM Fixtures

Jeder Provider bekommt Fixtures:

```text
survey-cli/tests/fixtures/providers/
  qualtrics_language.html
  qualtrics_radio.html
  qualtrics_complete.html
  toluna_radio.html
  strat7_radio.html
  purespectrum_angular.html
```

## Tests

| Test | Erwartung |
|---|---|
| `test_qualtrics_language_selects_and_nexts` | Deutschland + Next erzeugt zwei Actions |
| `test_qualtrics_next_button_detected_on_container` | `.NextButton` wird gefunden |
| `test_leaf_node_parent_container_kept` | Parent containers nicht weggefiltert |
| `test_provider_registry_picks_by_url_and_dom` | URL + DOM detection |
| `test_provider_completion_contract` | completed/screen_out/blocked eindeutig |
| `test_purespectrum_uses_trusted_mouse_event` | kein normales `.click()` fuer Angular |

## Arbeitsschritte

1. `providers/base.py` bauen.
2. `ProviderRegistry` bauen.
3. QualtricsAdapter als erster echter Adapter.
4. `execute.py` auf Adapter delegieren, Provider-Dict reduzieren.
5. Snapshot scanner fuer parent containers erweitern.
6. CompletionDetector provider-aware machen.
7. Toluna/Strat7/PureSpectrum nachziehen.

## Verification

```bash
pytest survey-cli/tests/test_snapshot.py survey-cli/tests/test_execute.py -q
pytest survey-cli/tests/test_providers.py -q
rg "qualtrics|toluna|strat7|purespectrum" survey-cli/survey/runner.py
```

## Exit-Kriterien

- Qualtrics language page kann automatisch weiter.
- Provider-Wissen liegt in `providers/`, nicht in `runner.py`.
- Jeder Adapter hat DOM-Fixture-Tests.
