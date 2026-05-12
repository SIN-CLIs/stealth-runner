# SR-151 — Residential Proxy Pool + IP-Quality Scoring

## Context

Anti-detection has 3 layers: fingerprint (covered by `stealth/injection.js` + `daemon/stealth.py`), behavior (covered by mouse-jitter + answer-timing), and network. **Network is the open gap.** All requests today exit from the same datacenter IP. Heypiggy and downstream panels (Lucid in particular) block aggressive accounts within hours when an IP earns more than 2 cents/min — a fingerprint they actively monitor.

## Goal

Add a proxy-pool manager that:
1. Loads a configurable pool of HTTP/HTTPS/SOCKS5 residential proxies from env / config file
2. Scores each proxy on success rate, mean response time, ban-event count
3. Rotates proxies per-session with sticky-IP behavior inside a single survey (don't change IP mid-survey)
4. Falls back to direct connection with a logged warning when pool is exhausted
5. Provides a CLI command `survey proxy-status` to inspect pool health

**Zero paid services.** Pool entries come from user-provided env vars / config — the project doesn't ship with credentials. Bring-your-own-proxies (BYOP).

## Files

### NEW (4)
- `survey-cli/survey/network/proxy_pool.py` — pool manager + selection policy
- `survey-cli/survey/network/ip_quality.py` — score calculator + JSONL persistence
- `survey-cli/survey/network/__init__.py` — package marker, exports
- `survey-cli/tests/test_proxy_pool.py` — 16+ tests (selection, scoring, rotation, exhaustion)

### MODIFY (2)
- `survey-cli/survey/daemon/browser_driver.py`
  - Accept `proxy: ProxyEntry | None = None` in browser-launch path
  - Translate to Chrome CLI flag `--proxy-server=http://...` (or SOCKS5)
- `survey-cli/survey/daemon/cli.py`
  - Add `proxy-status` subcommand that prints the pool state as a table

## Config Format

User supplies a `proxies.yaml` (or `PROXY_POOL_JSON` env var) of the shape:

```yaml
- url: "http://user:pass@123.45.67.89:8080"
  label: "residential-de-1"
  country: "DE"
  type: "residential"
- url: "socks5://user:pass@98.76.54.32:1080"
  label: "residential-us-1"
  country: "US"
  type: "residential"
```

## Selection Policy

- **Sticky per session:** A single survey-run uses one proxy until completion / hard-fail
- **Score-weighted choice:** Random pick weighted by score (good proxies win more often, bad ones still get retried occasionally)
- **Country preference:** If `persona.country` is set, prefer matching country (bonus weight +50%)
- **Ban handling:** On 403 / 429 / known-block markers, decrement score by 10 and rotate

## IP-Quality Score

`Score = base(100) + success_count*2 - fail_count*5 - ban_count*10`

Clamped to `[0, 200]`. Score < 10 → flagged as cold (next-pick deprioritized but not deleted).

Persistence: `logs/ip-quality-<ISO8601-date>.jsonl` (append-only). Rotate daily.

## Acceptance Criteria

### proxy_pool.py
- [ ] `ProxyPool` class with `load_from_env() -> Self`, `load_from_yaml(path) -> Self`, `pick(persona=None) -> ProxyEntry | None`
- [ ] `ProxyEntry` dataclass: `url`, `label`, `country`, `type`, `score` (calculated property)
- [ ] `record_outcome(entry, success: bool, banned: bool = False)` updates score and persists to JSONL
- [ ] Thread-safe (multiple personas may run in parallel) — use `threading.Lock`
- [ ] Empty pool → `pick()` returns None and logs WARN once per 60 seconds

### ip_quality.py
- [ ] `score(entry: ProxyEntry) -> int` matches formula above
- [ ] `persist_event(entry, outcome)` appends JSONL line: `{ts, label, country, outcome, score_before, score_after}`
- [ ] Daily rotation: writes go to file with today's UTC date in name

### CLI integration
- [ ] `survey proxy-status` prints table: label, country, score, success_count, fail_count, ban_count, last_used
- [ ] Exit code 0 if pool is healthy (≥ 1 entry with score ≥ 50), non-zero otherwise

### browser_driver.py wiring
- [ ] `BrowserDriver.__init__` accepts optional `proxy: ProxyEntry`
- [ ] When `proxy` is provided, Chrome launches with `--proxy-server=<url>` and `--proxy-bypass-list=<csv>` (use a sensible default that excludes localhost)
- [ ] When the browser session ends, `BrowserDriver` calls `pool.record_outcome(proxy, success=...)` based on the final survey outcome

### Tests (test_proxy_pool.py)
- [ ] Load from env: 3 entries (good test data), pool reports correct length
- [ ] Load from yaml: same
- [ ] Pick on empty pool → None + WARN logged
- [ ] Pick prefers entries with higher score (statistical: 1000 picks, top-scored entry > 50% picks)
- [ ] Country preference: persona country=DE → DE proxy picked > 70% of 1000 picks
- [ ] record_outcome success: score increases by 2
- [ ] record_outcome fail: score decreases by 5
- [ ] record_outcome banned: score decreases by 10
- [ ] Score clamping: never below 0, never above 200
- [ ] JSONL persistence: writes are append-only, format matches schema
- [ ] Sticky session: pick() called twice in same session → returns same entry
- [ ] Thread safety: 4 concurrent threads picking from pool of 2 — no exceptions, no duplicate-mutate corruption
- [ ] `survey proxy-status` exits 0 when ≥ 1 entry has score ≥ 50
- [ ] `survey proxy-status` exits 1 when pool is empty
- [ ] `survey proxy-status` exits 2 when pool has only "cold" entries (score < 10)
- [ ] BrowserDriver-with-proxy integration: mocked Chrome launch receives `--proxy-server` flag

### Quality
- [ ] ruff clean (E,W,F line-length 100, py312)
- [ ] No new pip deps (use stdlib `urllib.request.ProxyHandler` for any validation calls; PyYAML may be added if not yet present)
- [ ] Closes #151 in commit + PR body
- [ ] Branch: `feat/151-proxy-pool`

## Out of Scope

- Built-in proxy provider (no Bright Data SDK, no Oxylabs, no IPRoyal SDK — BYOP only)
- IP-quality scoring for the captcha solver (SR-138 chain is independent)
- DNS-over-HTTPS / WebRTC IP leak prevention beyond what `injection.js` already covers
- Question-type work (SR-150 owns)
- Reliability/DLQ work (SR-152 owns)

## References

- Browser launch path: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/browser_driver.py
- Existing stealth layer: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/stealth/injection.js
- Chrome proxy CLI docs: https://www.chromium.org/developers/design-documents/network-settings/

## Parallel-Safety

Zero file overlap with SR-150 or SR-152.

## Dependencies

None.
