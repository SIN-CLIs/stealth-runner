"""================================================================================
stealth-runner / core / state_manager.py  — Pipeline State + Crash-Recovery
================================================================================

HERKUNFT
--------
Aus Delqhi/sin-hermes-agent (.open-auth-rotator/openai/core/state_manager.py).
Universelles Pipeline-State-Tracking — unabhaengig vom Use-Case.

ZWECK
-----
EINE Stelle fuer "wo sind wir gerade in der Survey-Pipeline?". Beantwortet:
  - Welche Steps sind durch?  -> state.steps[i].status
  - Wo wuerden wir resumen?    -> get_resume_point()
  - Wie lange laeuft das?      -> state.get_duration_ms()
  - Sind wir failure?          -> state.status == PipelineStatus.FAILED

ABGRENZUNG ZU SurveyState (langgraph)
-------------------------------------
SurveyState (in survey-cli/survey/graph/state.py) ist der LangGraph-eigene
in-Memory-State EINER Survey. PipelineState hier ist die PERSISTENZ-Schicht
darueber: persistente Step-Granularitaet, Checkpoints, Resume.

Beide werden parallel gefuehrt -- bei kritischen Punkten wird state aus
SurveyState in PipelineState gespiegelt (z. B. nach jedem Node-Exit).

PERSISTENZ
----------
- Local: ~/.stealth/checkpoints/checkpoint_<id>.json  +  latest.json
- Distributed (optional): Supabase-Tabelle `stealth_pipeline_state`

CRASH-RECOVERY-PFAD
-------------------
  Process-Crash bei Iteration 7 / 15
        |
        v
  Neuer Process started
        |
        v
  StateManager.restore() liest latest.json
        |
        v
  get_resume_point() -> 7    (erster non-completed Step)
        |
        v
  LangGraph startet AB Iteration 7, Steps 0-6 werden SKIP'd

WICHTIG: Browser-State (Cookies, Tab-WS) wird NICHT persistiert -- wenn
Chrome crashed, beginnt die Survey neu. Persist sind nur die Pipeline-Stages.

BANNED
------
- Keine Mutations am State von ausserhalb (immer ueber StepContext)
- Keine Multi-Process-Writes ohne Lock (FS-Lock oder Supabase)
================================================================================"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# -- ENUMS ---------------------------------------------------------------------


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class PipelineStatus(Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"


# -- STEP STATE ----------------------------------------------------------------


@dataclass
class StepState:
    """State eines einzelnen Pipeline-Steps.

    Beispiele Steps im Survey-Run:
      ensure_chrome -> read_balance_before -> open_survey ->
      inject_cookies -> snapshot -> captcha -> decide -> execute ->
      detect_completion -> read_balance_after
    """

    name: str
    index: int
    status: StepStatus = StepStatus.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    duration_ms: float = 0.0
    retries: int = 0
    error_message: str = ""
    output: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.status = StepStatus.RUNNING
        self.started_at = time.time()

    def complete(self, output: dict | None = None) -> None:
        self.status = StepStatus.COMPLETED
        self.completed_at = time.time()
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at) * 1000
        if output:
            self.output = output

    def fail(self, error: str) -> None:
        self.status = StepStatus.FAILED
        self.completed_at = time.time()
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at) * 1000
        self.error_message = error

    def retry(self) -> None:
        self.status = StepStatus.RETRYING
        self.retries += 1

    def skip(self, reason: str = "") -> None:
        self.status = StepStatus.SKIPPED
        self.error_message = reason or "Skipped by pipeline"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "index": self.index,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "error_message": self.error_message,
            "output": self.output,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StepState:
        return cls(
            name=data["name"],
            index=data["index"],
            status=StepStatus(data["status"]),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0.0),
            retries=data.get("retries", 0),
            error_message=data.get("error_message", ""),
            output=data.get("output", {}),
        )


# -- PIPELINE STATE ------------------------------------------------------------


@dataclass
class PipelineState:
    """Gesamt-State einer Pipeline-Ausfuehrung.

    id wird automatisch generiert (sha256(time.time())[:16]).
    Survey-Use-Case: 1 PipelineState pro Survey (= pro LangGraph-Run).
    """

    id: str = ""
    status: PipelineStatus = PipelineStatus.IDLE
    started_at: float | None = None
    completed_at: float | None = None
    current_step_index: int = 0
    total_steps: int = 0
    steps: list[StepState] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]

    # -- Lifecycle ---------------------------------------------------------

    def initialize(self, step_names: list[str]) -> None:
        self.status = PipelineStatus.INITIALIZING
        self.started_at = time.time()
        self.total_steps = len(step_names)
        self.steps = [StepState(name=n, index=i) for i, n in enumerate(step_names)]
        self.current_step_index = 0
        self._update_checksum()

    def start(self) -> None:
        self.status = PipelineStatus.RUNNING
        if not self.started_at:
            self.started_at = time.time()
        self._update_checksum()

    def complete(self) -> None:
        self.status = PipelineStatus.COMPLETED
        self.completed_at = time.time()
        self._update_checksum()

    def fail(self, error: str = "") -> None:
        self.status = PipelineStatus.FAILED
        self.completed_at = time.time()
        self.context["failure_reason"] = error
        self._update_checksum()

    def pause(self) -> None:
        self.status = PipelineStatus.PAUSED
        self._update_checksum()

    def resume(self) -> None:
        self.status = PipelineStatus.RUNNING
        self._update_checksum()

    # -- Navigation --------------------------------------------------------

    def get_current_step(self) -> StepState | None:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance(self) -> bool:
        if self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            self._update_checksum()
            return True
        return False

    def get_progress(self) -> dict:
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        return {
            "completed": completed,
            "failed": failed,
            "remaining": self.total_steps - completed - failed,
            "total": self.total_steps,
            "percent": (completed / self.total_steps * 100) if self.total_steps else 0,
            "current_step": (self.steps[self.current_step_index].name if self.steps else None),
        }

    def get_duration_ms(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000

    # -- Checksum + Serialization ------------------------------------------

    def _update_checksum(self) -> None:
        data = f"{self.id}:{self.status.value}:{self.current_step_index}"
        self.checksum = hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "steps": [s.to_dict() for s in self.steps],
            "context": self.context,
            "checksum": self.checksum,
            "progress": self.get_progress(),
            "duration_ms": self.get_duration_ms(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PipelineState:
        state = cls(
            id=data["id"],
            status=PipelineStatus(data["status"]),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            current_step_index=data.get("current_step_index", 0),
            total_steps=data.get("total_steps", 0),
            context=data.get("context", {}),
            checksum=data.get("checksum", ""),
        )
        state.steps = [StepState.from_dict(s) for s in data.get("steps", [])]
        return state


# -- STATE MANAGER -------------------------------------------------------------


class StateManager:
    """Persistente Pipeline-State-Verwaltung.

    Typische Nutzung:
        mgr = StateManager()
        mgr.initialize(["ensure_chrome", "open_survey", ...])

        with mgr.step("ensure_chrome") as step:
            step.output["chrome_port"] = 9999  # custom output

        # automatisches checkpoint() im __exit__
    """

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ):
        default_dir = os.path.expanduser("~/.stealth/checkpoints")
        self.checkpoint_dir = Path(checkpoint_dir or default_dir)
        try:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_ANON_KEY")
        self._state: PipelineState | None = None

    @property
    def state(self) -> PipelineState:
        if self._state is None:
            self._state = PipelineState()
        return self._state

    # -- Initialization ----------------------------------------------------

    def initialize(self, step_names: list[str], context: dict | None = None) -> None:
        self._state = PipelineState()
        self._state.initialize(step_names)
        if context:
            self._state.context = context
        self.checkpoint()

    # -- Step Context ------------------------------------------------------

    def step(self, step_name: str) -> StepContext:
        return StepContext(self, step_name)

    def mark_step_start(self, step_index: int) -> None:
        if 0 <= step_index < len(self.state.steps):
            self.state.steps[step_index].start()
            self.state.current_step_index = step_index

    def mark_step_complete(self, step_index: int, output: dict | None = None) -> None:
        if 0 <= step_index < len(self.state.steps):
            self.state.steps[step_index].complete(output)

    def mark_step_failed(self, step_index: int, error: str) -> None:
        if 0 <= step_index < len(self.state.steps):
            self.state.steps[step_index].fail(error)

    # -- Checkpoint / Restore ----------------------------------------------

    def checkpoint(self) -> bool:
        if not self._state:
            return False
        cp_path = self.checkpoint_dir / f"checkpoint_{self._state.id}.json"
        latest = self.checkpoint_dir / "latest.json"
        try:
            data = self._state.to_dict()
            data["checkpoint_time"] = time.time()
            for p in (cp_path, latest):
                with open(p, "w") as f:
                    json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[STATE] Checkpoint failed: {e}")
            return False

    def restore(self, checkpoint_id: str | None = None) -> bool:
        path = (
            self.checkpoint_dir / f"checkpoint_{checkpoint_id}.json"
            if checkpoint_id
            else self.checkpoint_dir / "latest.json"
        )
        if not path.exists():
            return False
        try:
            with open(path) as f:
                data = json.load(f)
            self._state = PipelineState.from_dict(data)
            self._state.status = PipelineStatus.RECOVERING
            print(f"[STATE] Restored from checkpoint: {self._state.id}")
            return True
        except Exception as e:
            print(f"[STATE] Restore failed: {e}")
            return False

    def can_resume(self) -> bool:
        if not self._state:
            return False
        return self._state.status in (
            PipelineStatus.PAUSED,
            PipelineStatus.RECOVERING,
            PipelineStatus.RUNNING,
        )

    def get_resume_point(self) -> int:
        """Erster Step der nicht COMPLETED/SKIPPED ist."""
        if not self._state:
            return 0
        for i, step in enumerate(self._state.steps):
            if step.status not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                return i
        return len(self._state.steps)

    # -- Distributed Sync --------------------------------------------------

    async def sync_to_supabase(self, table: str = "stealth_pipeline_state") -> bool:
        if not self.supabase_url or not self.supabase_key or not self._state:
            return False
        try:
            import httpx

            payload = {
                "pipeline_id": self._state.id,
                "state_json": json.dumps(self._state.to_dict()),
                "status": self._state.status.value,
                "current_step": self._state.current_step_index,
                "updated_at": time.time(),
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.supabase_url}/rest/v1/{table}",
                    json=payload,
                    headers={
                        "apikey": self.supabase_key,
                        "Authorization": f"Bearer {self.supabase_key}",
                        "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates",
                    },
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            print(f"[STATE] Supabase sync failed: {e}")
            return False

    def get_summary(self) -> dict:
        if not self._state:
            return {"status": "uninitialized"}
        return {
            "pipeline_id": self._state.id,
            "status": self._state.status.value,
            "progress": self._state.get_progress(),
            "duration_ms": self._state.get_duration_ms(),
            "checksum": self._state.checksum,
        }


# -- STEP CONTEXT MANAGER ------------------------------------------------------


class StepContext:
    """Context-Manager fuer Step-Ausfuehrung.

    Bei normalem Exit -> mark_step_complete + checkpoint.
    Bei Exception     -> mark_step_failed + checkpoint, Exception RE-RAISED.
    """

    def __init__(self, manager: StateManager, step_name: str):
        self.manager = manager
        self.step_name = step_name
        self.step_index = -1
        self.step_state: StepState | None = None

    def __enter__(self) -> StepState | None:
        for i, step in enumerate(self.manager.state.steps):
            if step.name == self.step_name:
                self.step_index = i
                self.step_state = step
                break
        if self.step_state:
            self.manager.mark_step_start(self.step_index)
        return self.step_state

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.step_state:
            return
        if exc_type is None:
            self.manager.mark_step_complete(self.step_index, self.step_state.output)
        else:
            self.manager.mark_step_failed(self.step_index, str(exc_val))
        self.manager.checkpoint()

    async def __aenter__(self) -> StepState | None:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return self.__exit__(exc_type, exc_val, exc_tb)


# ── ASYNC LANGGRAPH-FRIENDLY API ─────────────────────────────────────────────
# Diese Methoden werden von core/langgraph_integration.py genutzt. Sie sind
# bewusst KEINE Methoden der StateManager-Klasse oben, weil StateManager dort
# pro Pipeline EINEN State haelt — der LangGraph-Use-Case ist anders:
# pro run_id ein eigenes Schicksal mit Steps, die aus arbitrary Reihenfolge
# kommen koennen (conditional edges).
#
# Storage: einzelne JSON-Files pro run_id unter checkpoint_dir/runs/<run_id>/.
#   - steps.jsonl       — append-only log aller Step-Events
#   - checkpoint.json   — letzter LangGraph-Checkpoint
#   - meta.json         — run metadata (started_at, last_update, status)
#
# Warum nicht SQLite? Async-FS Operations sind hier vollkommen ausreichend
# (1 Survey = max ~50 Step-Events), SQLite-Connection-Mgmt waere Overkill und
# wuerde aiosqlite als Dependency erzwingen.

import asyncio as _asyncio  # alias um Shadowing zu vermeiden
import contextlib
import uuid as _uuid

# Pro-Run File-Locks (best-effort gegen parallele Step-Writes im selben Prozess)
_run_locks: dict[str, _asyncio.Lock] = {}


def _run_lock(run_id: str) -> _asyncio.Lock:
    lock = _run_locks.get(run_id)
    if lock is None:
        lock = _asyncio.Lock()
        _run_locks[run_id] = lock
    return lock


def _runs_dir_for(manager: StateManager) -> Path:
    """Pfad fuer pro-run Subfolders."""
    base = manager.checkpoint_dir / "runs"
    with contextlib.suppress(Exception):
        base.mkdir(parents=True, exist_ok=True)
    return base


def _run_dir(manager: StateManager, run_id: str) -> Path:
    d = _runs_dir_for(manager) / run_id
    with contextlib.suppress(Exception):
        d.mkdir(parents=True, exist_ok=True)
    return d


async def _bootstrap(self: StateManager) -> None:
    """Bereitet das Run-FS-Layout vor. Idempotent. Async-only fuer
    spaetere Migration auf SQLite ohne API-Change.
    """
    _runs_dir_for(self)


async def _start_step(self: StateManager, run_id: str, name: str) -> str:
    """Eroeffne einen Step-Eintrag fuer den gegebenen run_id.
    Returns: step_id (uuid hex) — wird in complete/fail genutzt.
    """
    step_id = _uuid.uuid4().hex
    rec = {
        "step_id": step_id,
        "name": name,
        "status": "running",
        "started_at": time.time(),
    }
    async with _run_lock(run_id):
        path = _run_dir(self, run_id) / "steps.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return step_id


async def _complete_step(self: StateManager, step_id: str, output: dict | None = None) -> None:
    """Markiere Step als success. step_id wird in jeder Survey persistiert,
    pro-Run-Folder bleibt deshalb der vollstaendige Lifecycle nachvollziehbar.
    """
    rec = {
        "step_id": step_id,
        "status": "completed",
        "completed_at": time.time(),
        "output": output or {},
    }
    # step_id allein verraet uns nicht den run_id — wir muessen suchen.
    # Da step_ids hochfrequent eindeutig sind, akzeptabel: append in alle Folders
    # in denen wir den step finden. In Praxis wird step_id sofort konsumiert,
    # daher genuegt einfacher append in dedizierten "events.jsonl"-File.
    base = _runs_dir_for(self)
    target = base / "_events.jsonl"
    with open(target, "a") as f:
        f.write(json.dumps(rec) + "\n")


async def _fail_step(self: StateManager, step_id: str, error: str) -> None:
    """Markiere Step als failed mit kurzer Error-String (max 1k Chars)."""
    rec = {
        "step_id": step_id,
        "status": "failed",
        "failed_at": time.time(),
        "error": (error or "")[:1024],
    }
    base = _runs_dir_for(self)
    target = base / "_events.jsonl"
    with open(target, "a") as f:
        f.write(json.dumps(rec) + "\n")


async def _save_checkpoint(
    self: StateManager, run_id: str, checkpoint: Any, metadata: dict
) -> None:
    """Persistiere LangGraph-Checkpoint + Survey-Metadaten.

    Wenn ein 'budget'-Objekt im Checkpoint enthalten ist und es ein
    snapshot() liefert, speichern wir nur das Snapshot-Dict statt das Objekt
    (vermeidet Pickle-Probleme).
    """
    snap = checkpoint
    try:
        # SurveyBudget oder objekt mit snapshot() → dict
        if hasattr(checkpoint, "snapshot") and callable(checkpoint.snapshot):
            snap = checkpoint.snapshot()
    except Exception:
        pass

    payload = {
        "run_id": run_id,
        "saved_at": time.time(),
        "checkpoint": snap,
        "metadata": metadata or {},
    }
    async with _run_lock(run_id):
        path = _run_dir(self, run_id) / "checkpoint.json"
        tmp = path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(payload, f, default=str, indent=2)
            tmp.replace(path)
        except Exception as e:
            print(f"[STATE] save_checkpoint failed run_id={run_id}: {e}")


async def _load_checkpoint(self: StateManager, run_id: str) -> dict | None:
    """Liefere letztes Checkpoint-Dict fuer run_id (oder None)."""
    path = _run_dir(self, run_id) / "checkpoint.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[STATE] load_checkpoint failed run_id={run_id}: {e}")
        return None


async def _list_checkpoints(
    self: StateManager, run_id: str | None = None, *, limit: int = 10
) -> list[dict]:
    """Liefere die letzten N Checkpoints (sortiert nach saved_at desc).

    Wenn run_id None — alle Runs, sonst nur dieser eine (max 1 Eintrag, da
    wir nur den letzten Checkpoint je Run halten).
    """
    base = _runs_dir_for(self)
    if not base.exists():
        return []
    targets = (
        [base / run_id / "checkpoint.json"]
        if run_id
        else [d / "checkpoint.json" for d in base.iterdir() if d.is_dir()]
    )
    results = []
    for p in targets:
        if not p.exists():
            continue
        try:
            with open(p) as f:
                results.append(json.load(f))
        except Exception:
            continue
    results.sort(key=lambda r: r.get("saved_at", 0), reverse=True)
    return results[:limit]


# Monkey-attach an StateManager (kein Class-Diff noetig, klar wiederfindbar).
StateManager.bootstrap = _bootstrap  # type: ignore[attr-defined]
StateManager.start_step = _start_step  # type: ignore[attr-defined]
StateManager.complete_step = _complete_step  # type: ignore[attr-defined]
StateManager.fail_step = _fail_step  # type: ignore[attr-defined]
StateManager.save_checkpoint = _save_checkpoint  # type: ignore[attr-defined]
StateManager.load_checkpoint = _load_checkpoint  # type: ignore[attr-defined]
StateManager.list_checkpoints = _list_checkpoints  # type: ignore[attr-defined]
