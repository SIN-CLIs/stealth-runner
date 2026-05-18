"""================================================================================
LANGGRAPH CHECKPOINTER — Resume after crash without double-effects [SR-238]
================================================================================

WAS IST DAS?
  LangGraph-native Persistence-Layer fuer den Survey-Graph. Bei jedem Node-
  Uebergang wird der State (SurveyState) in eine SQLite-DB geschrieben. Wenn
  der Daemon mitten in einem Survey crasht, kann derselbe Survey via gleicher
  thread_id resumed werden — der Graph springt zur letzten gespeicherten
  Position und macht weiter.

  Das ergaenzt SR-237 (cash_out idempotency ledger): die Ledger schuetzt vor
  Doppel-Ausloesen der real-money side effects, dieser Checkpointer schuetzt
  vor Verlust des Survey-Fortschritts.

WAS IST NEU IM VERGLEICH ZU `core/langgraph_integration.CoreCheckpointer`?
  * Der bestehende `CoreCheckpointer` implementiert nur ein Subset des
    LangGraph-API (aput/aget/alist) und ist NICHT als BaseCheckpointSaver
    registriert. Er wird auch nirgendwo an `graph.compile(checkpointer=...)`
    uebergeben — d.h. der Graph laeuft bisher OHNE LangGraph-native
    Persistence. Was der `CoreCheckpointer` macht ist ein post-mortem
    snapshot via StateManager.save_checkpoint nach dem Run, nicht ein
    pro-superstep-Checkpoint waehrend des Runs.
  * Dieses Modul bietet einen `BaseCheckpointSaver`-konformen SqliteSaver
    der DIREKT in `graph.compile(checkpointer=...)` gegeben wird. LangGraph
    schreibt dann nach jedem Superstep einen vollstaendigen State-Snapshot
    in die SQLite-DB unter dem `thread_id`-Schluessel.

WHY SQLITE NOT POSTGRES?
  Aktuell ein Account, lokales Deployment, 1-10 Surveys/Tag. SQLite-Datei
  unter `$STATE_DIR/langgraph_checkpoints.db` ist genug; bei Multi-Account
  Skalierung (Welle 3) wechseln wir auf `langgraph.checkpoint.postgres.
  PostgresSaver` mit derselben API.

WHY THREAD_ID = f"{provider}:{survey_id}:{attempt}"?
  Stabil pro (Provider, Survey, Attempt). Resume nach Crash nutzt den
  gleichen Trippel. Zweiter Versuch der gleichen Survey nach Vollabbruch:
  attempt=1, neuer thread_id, sauberer Lauf. Provider-Prefix verhindert
  Kollision falls zwei Provider die gleiche numerische Survey-ID haben.

CONTRACT
--------
- `get_default_checkpoint_path(state_dir)` -> Path
    Liefert `$STATE_DIR/langgraph_checkpoints.db` (Default-Path).
- `create_sqlite_checkpointer(path=None) -> Saver | None`
    Liefert einen SqliteSaver. None wenn langgraph oder dessen sqlite
    extra fehlen — Caller muss damit umgehen koennen.
- `make_thread_id(state, attempt=0) -> str`
    Stabiler thread_id-String, unabhaengig von State-Mutationen waehrend
    des Runs.
- `make_run_config(state, *, attempt=0)` -> dict
    Fertige `config={"configurable": {"thread_id": ...}}` Struktur fuer
    `compiled.invoke(state, config=...)`.

DESIGN-PRINZIP
--------------
- SqliteSaver ist OPTIONAL. Wenn `langgraph` nicht installiert ist
  (Lint-Hosts, Sandbox), liefert `create_sqlite_checkpointer()` None und
  `create_graph()` faellt auf "kein Checkpointing" zurueck. Der bestehende
  pfad bleibt 1:1 funktional.
- thread_id ist deterministisch ableitbar — kein UUID-Rand. Dadurch ist
  Resume zero-config: derselbe (provider, survey_id, attempt) gibt
  denselben thread_id, der LangGraph automatisch wieder aufgreift.
- Path ist via `STATE_DIR` env-overridebar (Tests) und faellt auf
  `<package>/state/` zurueck — gleiche Konvention wie cash_out_ledger.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CHECKPOINT_DB_NAME = "langgraph_checkpoints.db"


def get_default_checkpoint_path(state_dir: Optional[Path] = None) -> Path:
    """Return the default SQLite path under STATE_DIR (or its fallback).

    Honour STATE_DIR env var if set (tests, container deployments). Else
    fall back to `<survey-cli>/state/`. Same policy as the cash-out
    ledger so a single STATE_DIR override moves both files.
    """
    if state_dir is not None:
        base = Path(state_dir)
    else:
        env = os.environ.get("STATE_DIR")
        if env:
            base = Path(env)
        else:
            # `<survey-cli>/state/` — `__file__` lives at
            # survey-cli/survey/graph/checkpointer.py.
            base = Path(__file__).resolve().parent.parent.parent / "state"
    base.mkdir(parents=True, exist_ok=True)
    return base / CHECKPOINT_DB_NAME


def make_thread_id(
    state: Any,
    *,
    attempt: int = 0,
    fallback: str = "unknown",
) -> str:
    """Deterministic thread_id from a SurveyState-shaped object.

    `state` is duck-typed — we only need `survey_id` and `provider`
    attributes. This keeps the helper usable from tests without
    importing the full SurveyState dataclass.

    Args:
        state: any object exposing .survey_id and .provider
        attempt: bump this on a fresh attempt of the same survey to
            start a new thread (clean state, no resume).
        fallback: replacement string when survey_id or provider are
            empty — should not happen in production but keeps tests
            deterministic.
    """
    sid = (getattr(state, "survey_id", "") or fallback).strip() or fallback
    provider = (getattr(state, "provider", "") or fallback).strip() or fallback
    safe_attempt = max(0, int(attempt))
    return f"{provider}:{sid}:{safe_attempt}"


def make_run_config(state: Any, *, attempt: int = 0) -> dict:
    """LangGraph `config=` dict for `compiled.invoke(state, config=...)`."""
    return {
        "configurable": {
            "thread_id": make_thread_id(state, attempt=attempt),
        }
    }


def create_sqlite_checkpointer(path: Optional[Path] = None) -> Optional[Any]:
    """Build a `langgraph.checkpoint.sqlite.SqliteSaver` for the given path.

    Returns None when:
      - `langgraph` is not installed (sandbox / lint hosts)
      - `langgraph.checkpoint.sqlite` is missing (older langgraph version)

    The function NEVER raises on missing extras; callers MUST treat None
    as "no checkpointing, run unprotected" and decide whether that's
    acceptable.

    Why no async variant here?
      The survey graph is sync (sync_node_with_core wraps every node). The
      sync SqliteSaver is the correct match. When we move to FastMCP/async
      we add a sibling helper for `AsyncSqliteSaver`.
    """
    try:
        # langgraph 0.2+: top-level `langgraph.checkpoint.sqlite.SqliteSaver`.
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[import-not-found]
    except ImportError:
        try:
            # Fallback for older / community packaging.
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "langgraph.checkpoint.sqlite not available — graph runs "
                "without crash-resume. Install `langgraph[sqlite]` for "
                "production durability.",
            )
            return None

    db_path = path or get_default_checkpoint_path()
    # SqliteSaver in langgraph 0.2 expects a sqlite3.Connection; from_conn_string
    # is the recommended factory.
    try:
        # 0.2+ API: classmethod context-manager. We open a real connection
        # so the returned saver outlives its `with` block — caller owns
        # cleanup.
        import sqlite3

        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        saver = SqliteSaver(conn)
        try:
            saver.setup()
        except Exception:
            # setup() is idempotent in 0.2+; older versions may not have it.
            pass
        logger.info("langgraph checkpointer: sqlite at %s", db_path)
        return saver
    except Exception as exc:  # pragma: no cover — defensive only
        logger.warning(
            "langgraph SqliteSaver init failed (%s) — running without "
            "checkpointing. db_path=%s", exc, db_path,
        )
        return None


__all__ = [
    "CHECKPOINT_DB_NAME",
    "get_default_checkpoint_path",
    "make_thread_id",
    "make_run_config",
    "create_sqlite_checkpointer",
]
