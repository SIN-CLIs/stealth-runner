# SR-159 — Observability + Alerting (Prometheus, structured logs, Sentry, Grafana)

## Context

`survey_daemon` runs 24/7 in production. When something goes wrong (NIM quota hit, captcha solver chain exhausted, proxy ban-window triggered) we currently find out *the next day* by manually grepping logs. Production-grade ops requires:
- **Metrics**: counters, gauges, histograms exposed on `/metrics` (Prometheus scrape)
- **Logs**: structured JSON via `structlog` (already in deps but not configured)
- **Traces**: lightweight, no OpenTelemetry yet — just span-id correlation in logs
- **Alerts**: Sentry for errors, webhook for SLO breaches
- **Dashboard**: Grafana JSON committed to repo for instant import

## Goal

Wire observability into the existing daemon. **No new languages, no new processes, no new SaaS** beyond:
- Prometheus self-scrape via `prometheus_client` (BSD license, pure Python)
- Sentry SDK via `sentry-sdk` (optional, gated on `SENTRY_DSN` env)
- structlog reconfigured for JSON output to stdout (consumed by Vercel logs, Loki, CloudWatch, anything)

## Files

### NEW (6)
- `survey-cli/survey/observability/prometheus.py` — `Counter`, `Gauge`, `Histogram` registry + `/metrics` endpoint
- `survey-cli/survey/observability/structlog_config.py` — structlog processors: timestamp, level, span-id, JSON renderer
- `survey-cli/survey/observability/sentry_init.py` — `init_sentry()` gated on `SENTRY_DSN`; configures `before_send` PII scrubbing
- `survey-cli/survey/observability/alerts.py` — `SLOBreachAlerter` (e.g., DLQ-size > 50 → webhook)
- `docs/grafana-dashboard.json` — exportable Grafana dashboard (12 panels)
- `survey-cli/tests/test_observability.py` — 18+ tests

### MODIFY (5)
- `survey-cli/survey/observability/__init__.py` — re-export all above
- `survey-cli/survey/daemon/survey_daemon.py` — increment counters at key points (survey-started, survey-completed, survey-failed, dlq-push, captcha-solve, captcha-fallback-step-N)
- `survey-cli/survey/captcha/fallback_chain.py` — `Histogram.observe(...)` per step latency
- `survey-cli/survey/network/proxy_pool.py` — gauge: pool-size, healthy-entries, scoreboard
- `pyproject.toml` — add `prometheus-client>=0.21`, `sentry-sdk>=2.18` (optional via extras)

## Detail: Prometheus Metrics

```python
# Naming follows the prometheus-best-practices contract
# https://prometheus.io/docs/practices/naming/

surveys_total = Counter(
    "surveys_total",
    "Surveys processed by outcome",
    labelnames=["provider", "outcome"],  # outcome: completed|disqualified|failed|dlq
)
survey_duration_seconds = Histogram(
    "survey_duration_seconds",
    "Survey end-to-end duration",
    labelnames=["provider"],
    buckets=(15, 30, 60, 120, 300, 600, 1200, 1800),
)
captcha_fallback_step = Counter(
    "captcha_fallback_step_total",
    "Captcha chain steps consumed by outcome",
    labelnames=["step", "outcome"],  # step: nim_primary|nim_secondary|gateway|audio|human
)
captcha_step_duration_seconds = Histogram(
    "captcha_step_duration_seconds",
    "Latency per captcha-chain step",
    labelnames=["step"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)
proxy_pool_healthy = Gauge(
    "proxy_pool_healthy_entries",
    "Number of proxies with score >= 50",
)
proxy_pool_score = Gauge(
    "proxy_pool_entry_score",
    "Per-proxy score",
    labelnames=["label", "country"],
)
dlq_pending = Gauge(
    "dlq_pending_records",
    "Pending DLQ entries (not yet replayed or discarded)",
)
contradiction_pinned = Counter(
    "contradiction_pinned_total",
    "Persona answers pinned by contradiction detector",
    labelnames=["category"],
)
```

`/metrics` endpoint is exposed via the existing FastAPI app at `/observability/metrics` (FastAPI is already in deps; pyproject shows `fastapi>=0.115`).

## Detail: Structured Logs

```python
# structlog_config.py
import structlog
import logging

def configure():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,    # span_id, survey_id propagation
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

Existing `survey/observability/logger.py` is preserved as a thin facade that forwards to structlog when `STEALTH_LOG_FORMAT=json`, else falls back to current format (backwards-compatible).

## Detail: Sentry

```python
# sentry_init.py
import os, sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

def init_sentry():
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return  # opt-in only
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.05,   # 5% of transactions sampled
        environment=os.environ.get("STEALTH_ENV", "production"),
        before_send=_scrub_pii,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
    )

def _scrub_pii(event, hint):
    # Persona PII: email, postal, full name → redacted before send
    ...
```

## Detail: SLO Breach Alerter

`SLOBreachAlerter` runs as a periodic task (every 60s) inside the daemon. Checks:

| SLO | Threshold | Action |
|---|---|---|
| Survey completion rate | < 60% in last hour | Webhook + Sentry log |
| DLQ pending records | > 50 | Webhook + Sentry log |
| Captcha step-5 (human handoff) | > 5 in last hour | Webhook + Sentry log |
| Proxy pool healthy | < 1 entry | Webhook + Sentry log (CRITICAL) |

Webhook URL via `RELIABILITY_WEBHOOK_URL` (same env as SR-152). Payload schema mirrors SR-152's webhook so users can pipe both to the same Slack/Discord.

## Detail: Grafana Dashboard

`docs/grafana-dashboard.json` — 12 panels arranged in 3 rows:
1. **Throughput row**: surveys/hour, surveys-by-outcome stacked, surveys-by-provider stacked, completion-rate gauge
2. **Captcha row**: chain step heatmap, step-latency p50/p95/p99, human-handoff rate, per-step success rate
3. **Infra row**: proxy pool health, DLQ size, contradiction pinning frequency, error log volume

User imports the dashboard JSON into their own Grafana instance pointing at their Prometheus scraping the daemon's `/observability/metrics` endpoint.

## Acceptance Criteria

### Metrics
- [ ] All 8 metrics listed above exist as module-level variables (re-importable)
- [ ] All daemon code paths that should observe (survey start/end/fail, captcha chain step, DLQ push, proxy pool change, contradiction pin) emit metrics
- [ ] `/observability/metrics` endpoint serves prometheus exposition format
- [ ] Endpoint returns 200 + correct content-type `text/plain; version=0.0.4`

### Structured Logs
- [ ] structlog configured via `configure_structlog()` called in daemon startup
- [ ] All logs include `timestamp` (iso, UTC), `level`, `event`, plus context vars
- [ ] When `STEALTH_LOG_FORMAT=json`, all output is valid JSONL
- [ ] When unset, behavior is identical to today (no regression)

### Sentry
- [ ] `init_sentry()` is opt-in via `SENTRY_DSN` env
- [ ] PII scrubbing strips `persona.email`, `persona.postal`, `persona.full_name` before send
- [ ] No-op when `SENTRY_DSN` is unset (no errors, no warnings)
- [ ] Sample rate is 5% for traces; 100% for errors

### Alerts
- [ ] `SLOBreachAlerter` is a class with `async def check_and_alert()` method
- [ ] 4 SLOs above are checked
- [ ] Alert fires at most once per 5 min per SLO (debounce)
- [ ] Daemon startup wires the alerter into the existing scheduler (APScheduler in deps)

### Dashboard
- [ ] `docs/grafana-dashboard.json` validates as Grafana 11 dashboard JSON
- [ ] All 12 panels reference metric names that match the daemon's emitted metrics
- [ ] Importing the JSON into a fresh Grafana shows panels with "No data" (not "metric not found")

### Tests (test_observability.py)
- [ ] 5 prometheus: metric registry, counter inc, histogram observe, gauge set, exposition format
- [ ] 4 structlog: configure, JSON output, context propagation, level filtering
- [ ] 3 sentry: init-with-dsn / init-without-dsn / PII scrubbing
- [ ] 4 alerter: SLO trigger / debounce / 4 SLOs each evaluable
- [ ] 2 endpoint: /observability/metrics 200, content-type correct

### Quality
- [ ] Branch: `feat/159-observability-alerting`
- [ ] Closes #159 in commit + PR body
- [ ] ruff clean (with SR-158's extended ruleset if landed)
- [ ] mypy --strict clean

## Out of Scope

- OpenTelemetry instrumentation (future)
- Distributed tracing (future; span-id correlation in logs is enough for now)
- Loki / CloudWatch shipping (deployment-specific; structured JSON output is sufficient for the daemon to be observable wherever logs land)
- Repo-reconciliation (SR-157 owns)
- CI hardening (SR-158 owns)

## Dependencies

- **Blocks on SR-157** (must know which path to use)
- Soft-depends on SR-152 (uses the DLQ size as one of the SLOs); SR-152's PR #156 must land first or the DLQ-SLO panel will be skipped with a warning

## References

- prometheus_client library: https://github.com/prometheus/client_python
- structlog best practices: https://www.structlog.org/en/stable/index.html
- sentry-sdk for Python: https://docs.sentry.io/platforms/python/
- Grafana dashboard JSON schema: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/import-dashboards/
- Existing observability dir: https://github.com/SIN-CLIs/stealth-runner/tree/main/survey-cli/survey/observability
- Existing FastAPI app: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/api.py (or wherever the FastAPI app lives — pre-flight: find it)

## Parallel-Safety

Touches `survey-cli/survey/observability/` (new files), the daemon (small surgical adds), pyproject (deps). Zero overlap with SR-158.
**Must run AFTER SR-157.**
