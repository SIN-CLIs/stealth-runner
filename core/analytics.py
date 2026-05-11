"""================================================================================
stealth-runner / core / analytics.py  — Metrics, Health-Checks, Prometheus-Export
================================================================================

HERKUNFT
--------
Aus Delqhi/sin-hermes-agent (.open-auth-rotator/openai/core/analytics.py).
Erweitert um survey-spezifische Health-Checks:
  - check_heypiggy_cookies()  -- sind Session-Cookies frisch?
  - check_captcha_quota()      -- hat 2captcha-Konto Guthaben?
  - check_chrome_cdp()         -- laeuft Bot-Chrome auf Port 9999?
  - check_supabase()           -- distributed state erreichbar?

ZWECK
-----
Drei Saeulen der Observability:

1. AnalyticsCollector
   - record(name, value, **labels)   -> Distribution + Percentiles
   - increment(name, **labels)        -> Counter
   - gauge(name, value, **labels)    -> Aktueller Wert
   - timer(name, **labels)            -> Context-Manager fuer Latency

2. MetricsExporter
   - to_json()                        -> fuer /metrics
   - to_prometheus()                  -> fuer /metrics/prometheus
   - push_to_supabase()               -> fuer zentrales Dashboard

3. HealthChecker
   - register(name, check_func)
   - check_all() -> ComponentHealth-Dict
   - get_overall_status() -> healthy | degraded | unhealthy

KEY-METRIKEN DIE WIR TRACKEN (fuer ROI)
---------------------------------------
  surveys_started_total               counter
  surveys_completed_total             counter        success-rate = completed/started
  surveys_screen_out_total            counter        screen-out-rate
  surveys_aborted_budget_total        counter        2-min Budget-Hits
  survey_duration_seconds             distribution   p50, p95, p99
  survey_earnings_eur                 distribution   target p50 > 0.30 EUR
  captcha_solved_total                counter
  captcha_failed_total                counter
  captcha_solve_duration_seconds      distribution   target p95 < 30s
  langgraph_node_duration_seconds     distribution   per-node, label=node
  langgraph_iterations                distribution   target p95 < 12

INTEGRATION
-----------
- get_collector()/get_health_checker() Singletons im core/__init__.py
- Jeder LangGraph-Node nutzt `with collector.timer("node_duration", node="..."):`
- /v2/health Endpoint ruft health_checker.check_all()
- /v2/metrics Endpoint ruft exporter.to_prometheus()

BANNED
------
- Keine Logging-Calls fuer Metriken (zu langsam, blockiert Async-Loop)
- Keine externen Metriken-Calls in Hot-Path-Code
================================================================================"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# -- METRIC-SAMPLE / STATS -----------------------------------------------------


@dataclass
class MetricSample:
    """Einzelner Messwert mit Timestamp + Labels."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricStats:
    """Aggregierte Statistik mit p50/p95/p99 fuer eine Metrik.

    samples ist gecappt auf 1000 (FIFO) -- Speicher-Limit. p95/p99 sind
    deshalb approximativ bei sehr hohem Throughput, fuer Survey-Use-Case
    (max 50 Surveys/Stunde) komplett ausreichend.
    """
    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    last: float = 0.0
    samples: list[float] = field(default_factory=list)

    def record(self, value: float, keep_samples: int = 1000) -> None:
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.last = value
        self.samples.append(value)
        if len(self.samples) > keep_samples:
            self.samples = self.samples[-keep_samples:]

    @property
    def avg(self) -> float:
        return self.sum / self.count if self.count > 0 else 0.0

    @property
    def p50(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        if len(self.samples) < 2:
            return self.last
        s = sorted(self.samples)
        return s[int(len(s) * 0.95)]

    @property
    def p99(self) -> float:
        if len(self.samples) < 2:
            return self.last
        s = sorted(self.samples)
        return s[int(len(s) * 0.99)]

    def to_dict(self) -> dict[str, float]:
        return {
            "count": self.count,
            "sum": self.sum,
            "min": self.min if self.min != float("inf") else 0,
            "max": self.max if self.max != float("-inf") else 0,
            "avg": self.avg,
            "last": self.last,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
        }


# -- COLLECTOR -----------------------------------------------------------------


class AnalyticsCollector:
    """Zentrale Metrik-Sammlung.

    Drei Typen:
      record()    : Distribution + Stats (latency, duration, size)
      increment() : Monotoner Counter
      gauge()     : Aktueller Wert (cpu, memory, queue_depth)

    Labels sind frei waehlbar -- sortierte Key-Liste wird zu einem Suffix
    `{k1=v1,k2=v2}` an den Metric-Namen gehaengt. Beispiel:
       record("node_duration", 0.42, node="captcha", provider="purespectrum")
       -> key = "node_duration{node=captcha,provider=purespectrum}"
    """

    def __init__(self):
        self._metrics: dict[str, MetricStats] = defaultdict(MetricStats)
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._start_time = time.time()
        self._labels: dict[str, str] = {}

    def set_labels(self, **labels) -> None:
        """Globale Labels die jeder Metrik automatisch angehaengt werden.
        Z. B. set_labels(env="production", region="eu") beim Startup."""
        self._labels.update(labels)

    def record(self, name: str, value: float, **labels) -> None:
        self._metrics[self._make_key(name, labels)].record(value)

    def increment(self, name: str, amount: int = 1, **labels) -> None:
        self._counters[self._make_key(name, labels)] += amount

    def gauge(self, name: str, value: float, **labels) -> None:
        self._gauges[self._make_key(name, labels)] = value

    def _make_key(self, name: str, labels: dict) -> str:
        all_labels = {**self._labels, **labels}
        if not all_labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(all_labels.items()))
        return f"{name}{{{label_str}}}"

    # -- Timer (Context-Manager, sync + async) ------------------------------

    class timer:
        """Misst Dauer eines With-Blocks. Funktioniert sync und async."""

        def __init__(self, collector: "AnalyticsCollector", name: str, **labels):
            self.collector = collector
            self.name = name
            self.labels = labels
            self.start = 0.0

        def __enter__(self):
            self.start = time.time()
            return self

        def __exit__(self, *args):
            self.collector.record(self.name, time.time() - self.start, **self.labels)

        async def __aenter__(self):
            self.start = time.time()
            return self

        async def __aexit__(self, *args):
            self.collector.record(self.name, time.time() - self.start, **self.labels)

    def timer(self, name: str, **labels) -> "AnalyticsCollector.timer":  # type: ignore[no-redef]
        return AnalyticsCollector.timer(self, name, **labels)

    # -- Read-API -----------------------------------------------------------

    def get_stats(self, name: str, **labels) -> Optional[dict]:
        key = self._make_key(name, labels)
        if key in self._metrics:
            return self._metrics[key].to_dict()
        return None

    def get_counter(self, name: str, **labels) -> int:
        return self._counters.get(self._make_key(name, labels), 0)

    def get_gauge(self, name: str, **labels) -> float:
        return self._gauges.get(self._make_key(name, labels), 0.0)

    def get_all_metrics(self) -> dict[str, Any]:
        return {
            "uptime_seconds": time.time() - self._start_time,
            "collected_at": datetime.now().isoformat(),
            "metrics": {k: v.to_dict() for k, v in self._metrics.items()},
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def reset(self) -> None:
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._start_time = time.time()


# -- EXPORTER ------------------------------------------------------------------


class MetricsExporter:
    """Export-Formate fuer /metrics und externe Sinks.

    Prometheus-Format ist text/plain, ein Eintrag pro Zeile.
    `# TYPE` und `# HELP` Kommentare sind optional aber empfohlen.
    """

    def __init__(self, collector: AnalyticsCollector):
        self.collector = collector

    def to_json(self) -> str:
        return json.dumps(self.collector.get_all_metrics(), indent=2)

    def to_prometheus(self) -> str:
        lines: list[str] = []
        lines.append("# HELP stealth_uptime_seconds Time since process start")
        lines.append("# TYPE stealth_uptime_seconds gauge")
        lines.append(
            f"stealth_uptime_seconds {time.time() - self.collector._start_time:.2f}"
        )
        for key, stats in self.collector._metrics.items():
            safe = key.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {safe} summary")
            lines.append(f"{safe}_count {stats.count}")
            lines.append(f"{safe}_sum {stats.sum:.4f}")
            lines.append(f"{safe}_avg {stats.avg:.4f}")
            lines.append(f"{safe}_p95 {stats.p95:.4f}")
        for key, value in self.collector._counters.items():
            safe = key.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {safe} counter")
            lines.append(f"{safe} {value}")
        for key, value in self.collector._gauges.items():
            safe = key.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {safe} gauge")
            lines.append(f"{safe} {value:.4f}")
        return "\n".join(lines)

    async def push_to_supabase(
        self, supabase_url: str, supabase_key: str, table: str = "stealth_metrics"
    ) -> bool:
        try:
            import httpx

            metrics = self.collector.get_all_metrics()
            payload = {
                "timestamp": datetime.now().isoformat(),
                "metrics_json": json.dumps(metrics),
                "uptime_seconds": metrics["uptime_seconds"],
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{supabase_url}/rest/v1/{table}",
                    json=payload,
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            print(f"[METRICS] Failed to push to Supabase: {e}")
            return False


# -- HEALTH-CHECKS -------------------------------------------------------------


@dataclass
class ComponentHealth:
    """Status einer einzelnen Komponente."""
    name: str
    status: str  # healthy | degraded | unhealthy
    latency_ms: float = 0.0
    last_check: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "last_check": datetime.fromtimestamp(self.last_check).isoformat(),
            "details": self.details,
        }


class HealthChecker:
    """Health-Check-Registry.

    register("name", async_check_func) -> check_func liefert (status, details)
    check_all() laeuft alle Checks parallel.

    Default-Checks werden vom core/__init__.py beim Erststart registriert.
    """

    def __init__(self):
        self._checks: dict[str, Callable] = {}
        self._results: dict[str, ComponentHealth] = {}

    def register(self, name: str, check_func: Callable) -> None:
        self._checks[name] = check_func

    async def check(self, name: str) -> ComponentHealth:
        if name not in self._checks:
            return ComponentHealth(
                name=name, status="unknown",
                details={"error": "check not registered"},
            )
        start = time.time()
        try:
            check_func = self._checks[name]
            if asyncio.iscoroutinefunction(check_func):
                status, details = await check_func()
            else:
                status, details = check_func()
            latency = (time.time() - start) * 1000
            health = ComponentHealth(
                name=name, status=status, latency_ms=latency, details=details or {},
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            health = ComponentHealth(
                name=name, status="unhealthy", latency_ms=latency,
                details={"error": str(e)},
            )
        self._results[name] = health
        return health

    async def check_all(self) -> dict[str, ComponentHealth]:
        await asyncio.gather(*[self.check(n) for n in self._checks])
        return self._results

    def get_overall_status(self) -> str:
        if not self._results:
            return "unknown"
        statuses = [h.status for h in self._results.values()]
        if all(s == "healthy" for s in statuses):
            return "healthy"
        if any(s == "unhealthy" for s in statuses):
            return "unhealthy"
        return "degraded"

    def to_dict(self) -> dict:
        return {
            "overall": self.get_overall_status(),
            "timestamp": datetime.now().isoformat(),
            "components": {name: h.to_dict() for name, h in self._results.items()},
        }


# -- DEFAULT-CHECKS (stealth-runner spezifisch) -------------------------------


async def check_chrome_cdp(port: int = 9999) -> tuple[str, dict]:
    """Bot-Chrome auf Port 9999 erreichbar?"""
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        ) as r:
            data = json.load(r)
            return "healthy", {"browser": data.get("Browser", "unknown"), "port": port}
    except Exception as e:
        return "unhealthy", {"error": str(e), "port": port}


async def check_supabase(url: str, key: str) -> tuple[str, dict]:
    """Supabase erreichbar fuer distributed state + audit-sync?"""
    if not url or not key:
        return "degraded", {"reason": "not_configured"}
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{url}/rest/v1/", headers={"apikey": key}, timeout=5.0
            )
            if resp.status_code == 200:
                return "healthy", {}
            return "degraded", {"status_code": resp.status_code}
    except Exception as e:
        return "unhealthy", {"error": str(e)}


def check_filesystem(paths: list[str]) -> tuple[str, dict]:
    """Pflicht-Pfade vorhanden? (Cookie-Backup, Log-Dir, Screenshot-Dir)"""
    results: dict[str, str] = {}
    for path in paths:
        try:
            results[path] = "accessible" if os.path.exists(path) else "not_found"
        except Exception as e:
            results[path] = f"error: {e}"
    if all(v == "accessible" for v in results.values()):
        return "healthy", results
    return "degraded", results


def check_heypiggy_cookies(cookie_path: str) -> tuple[str, dict]:
    """Sind HeyPiggy-Session-Cookies frisch?

    Schaut nach mtime der Datei. > 24h alt -> degraded (Re-Login bald noetig).
    > 7d alt -> unhealthy (vermutlich expired).
    """
    if not os.path.exists(cookie_path):
        return "unhealthy", {"reason": "file_not_found", "path": cookie_path}
    age_s = time.time() - os.path.getmtime(cookie_path)
    age_h = age_s / 3600
    details = {"age_hours": round(age_h, 1), "path": cookie_path}
    if age_h > 24 * 7:
        return "unhealthy", details
    if age_h > 24:
        return "degraded", details
    return "healthy", details


async def check_captcha_quota(api_key: str) -> tuple[str, dict]:
    """2captcha Konto-Balance pruefen.

    Empty key -> degraded (kein Fallback verfuegbar).
    Balance < 0.5 USD -> degraded (reicht fuer ~100 Captchas).
    """
    if not api_key:
        return "degraded", {"reason": "no_api_key"}
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://2captcha.com/res.php?key={api_key}&action=getbalance",
                timeout=5.0,
            )
            text = resp.text.strip()
            if text.startswith("ERROR"):
                return "unhealthy", {"error": text}
            balance = float(text)
            if balance < 0.5:
                return "degraded", {"balance_usd": balance, "warning": "low"}
            return "healthy", {"balance_usd": balance}
    except Exception as e:
        return "unhealthy", {"error": str(e)}
