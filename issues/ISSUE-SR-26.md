# SR-26 — Unit Tests: CDP Client + HitTester + Memory

| Feld | Wert |
|------|------|
| Status | 🟡 IN PROGRESS |
| Priority | 🟠 High |
| Created | 2026-05-05 |
| Labels | testing, python, unit-tests, cdp, stealth-suite |

---

## Kontext

`test_trajectory.py` (13 Tests) ist die einzige Test-Datei im `captchas/` Package. Folgende Module haben **0 Tests**:

- `cdp/client.py` — Async CDP WebSocket Client
- `primitives/hit_test.py` — Overlay detection + pointer-events
- `memory/experience.py` — SQLite Episodic Memory
- `primitives/verify.py` — DOM polling für .gc-success/.gc-fail
- `stealth/patches.py` — Stealth JS bundle injection

---

## Ziel

**Vor Annahme:** Alle public Module haben >= 1 Test-Datei mit >= 3 Tests pro Modul. Coverage-Ziel: >60%.

---

## Akzeptanzkriterien

### test_cdp_client.py
- [ ] `test_send_command_returns_parsed_response` — mock WebSocket, teste JSON-RPC request/response
- [ ] `test_invoke_with_params` — teste Parameter-Handling
- [ ] `test_session_multiplexing` — mehrere Targets, eine Connection
- [ ] `test_reconnect_on_disconnect` — Resilience test
- [ ] `test_input_dispatch_mouse_event` — verify correct CDP payload structure

### test_hit_test.py
- [ ] `test_element_from_point_returns_topmost` — mock page with stacked divs
- [ ] `test_overlay_detected` — SVG with pointer-events:auto blocks inner element
- [ ] `test_pointer_events_none_applied` — Verify style.pointerEvents='none' set
- [ ] `test_restore_pointer_events` — After drag, restore original
- [ ] `test_nested_iframe` — iframe inside overlay still detected

### test_memory.py
- [ ] `test_save_and_retrieve` — SQLite write/read roundtrip
- [ ] `test_similar_gap_query` — query returns similar past gaps
- [ ] `test_eviction_lru` — >max_entries triggers LRU eviction
- [ ] `test_clear_all` — memory-clear command works
- [ ] `test_stats` — record_count, avg_confidence reported correctly

### test_verify.py
- [ ] `test_gc_success_detected` — DOM contains .gc-success
- [ ] `test_gc_fail_detected` — DOM contains .gc-fail
- [ ] `test_polling_interval` — verify called every N ms
- [ ] `test_timeout_triggers` — returns error after N seconds

### test_patches.py
- [ ] `test_stealth_bundle_generates_valid_js` — JS string nicht leer, enthält key patterns
- [ ] `test_patches_applied_via_cdp` — Page.addScriptToEvaluateOnNewDocument called

---

## Technische Details

### Mocking Strategy
```python
# Für CDP Client: mock websockets WebSocketServerProtocol
# Für HitTester: parse HTML snippet mit minidom
# Für Memory: real SQLite in /tmp/ für isolation
# Für Verify: mock CDP session mit fake DOM strings
```

### Coverage Ziel
```
captchas/cdp/client.py       → 70%
captchas/primitives/hit_test.py → 80%
captchas/memory/experience.py → 75%
captchas/primitives/verify.py → 70%
captchas/stealth/patches.py   → 60%
Total Coverage                 → >60%
```

---

## Ressourcen

- `stealth-suite/py-packages/captchas/cdp/client.py`
- `stealth-suite/py-packages/captchas/primitives/hit_test.py`
- `stealth-suite/py-packages/captchas/memory/experience.py`
- `stealth-suite/py-packages/captchas/primitives/verify.py`
- `stealth-suite/py-packages/captchas/stealth/patches.py`
- `stealth-suite/py-packages/captchas/tests/test_trajectory.py` — als Referenz für Test-Style

---

## Geschätzter Aufwand

- **Time**: 3-5h
- **Difficulty**: Mittel ( mocking, HTML parsing, async)
- **Blocker**: Keine (Tests können unabhängig geschrieben werden)
