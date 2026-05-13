"""
SnapshotV2 — Question-level DOM state capture with stable subtree hashes.

Additive to ``survey.snapshot.CompactSnapshot``; SnapshotV2 focuses on
form-control state (value / checked / selected / aria-pressed) at the
*question* granularity. Hashes are deterministic so two consecutive captures
that produce the same hash imply DOM stability — used by the post-action
verifier (#167) to detect "nothing happened" / "DOM still re-rendering"
conditions, and as a foundation for Phase 2 idempotent-skip logic (#168).

Design constraints:
    * Pure-Python, no Playwright dependency at import time (driver is duck-typed).
    * One JS round-trip per snapshot (single ``evaluate`` call).
    * JSON-serializable result so AgentState (TypedDict-of-primitives) can hold it.
    * Stable canonical hash: ``sha256(json.dumps(node, sort_keys=True))``.

NOT in scope:
    * Visual / accessibility tree (use ``survey.accessibility``).
    * Cross-page diff (use ``CompactSnapshot``).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# JS that walks every form control + ``[data-question-id]`` subtree and
# returns a normalized array. Kept as a single string for one round-trip.
# ``role`` falls back to tag, ``name`` falls back to id/name/data-question-id.
_SNAPSHOT_JS = r"""
(() => {
  const norm = (s) => (s == null ? "" : String(s)).trim().slice(0, 512);
  const out = [];
  const seenQ = new Set();

  const controls = Array.from(document.querySelectorAll(
    'input, select, textarea, [role="radio"], [role="checkbox"], [role="slider"], [role="switch"]'
  ));

  for (const el of controls) {
    const tag = el.tagName.toLowerCase();
    const type = (el.type || el.getAttribute('type') || "").toLowerCase();
    const role = el.getAttribute('role') || tag;
    const qid =
      el.getAttribute('data-question-id') ||
      (el.closest('[data-question-id]')?.getAttribute('data-question-id')) ||
      el.name || el.id || "";

    let value = null;
    let checked = null;
    let selected = null;

    if (tag === 'input' && (type === 'checkbox' || type === 'radio')) {
      value = el.value;
      checked = !!el.checked;
    } else if (tag === 'select') {
      const opts = Array.from(el.selectedOptions || []).map((o) => o.value);
      value = el.multiple ? opts : (opts[0] ?? el.value);
      selected = opts;
    } else if (tag === 'input' || tag === 'textarea') {
      value = el.value;
    } else if (role === 'radio' || role === 'checkbox' || role === 'switch') {
      // ARIA controls — value lives in aria-checked / aria-pressed
      const a = el.getAttribute('aria-checked') ?? el.getAttribute('aria-pressed');
      checked = a === 'true';
      value = el.getAttribute('data-value') || norm(el.textContent);
    } else if (role === 'slider') {
      value = el.getAttribute('aria-valuenow') ?? el.value ?? null;
    }

    out.push({
      qid: norm(qid),
      tag, type, role,
      name: norm(el.name || el.id),
      value: Array.isArray(value) ? value.map(norm) : (value == null ? null : norm(value)),
      checked,
      selected: Array.isArray(selected) ? selected.map(norm) : null,
      disabled: !!el.disabled,
      visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
    });

    if (qid) seenQ.add(norm(qid));
  }

  // Also surface question containers that have no scanned controls (custom widgets)
  for (const q of document.querySelectorAll('[data-question-id]')) {
    const qid = norm(q.getAttribute('data-question-id'));
    if (qid && !seenQ.has(qid)) {
      out.push({ qid, tag: 'container', type: '', role: '', name: '',
                 value: null, checked: null, selected: null,
                 disabled: false, visible: true });
    }
  }

  return { url: location.href, controls: out };
})()
"""


class _DriverProto(Protocol):
    async def evaluate(self, js: str) -> Any: ...  # noqa: E704


@dataclass(frozen=True)
class QuestionFrame:
    """Per-question DOM slice. Hash is over the sorted control list."""
    qid: str
    controls: list[dict]
    subtree_hash: str

    def to_dict(self) -> dict:
        return {"qid": self.qid, "controls": self.controls, "subtree_hash": self.subtree_hash}


@dataclass(frozen=True)
class SnapshotV2:
    """
    Deterministic DOM-state capture grouped by ``data-question-id``.

    ``page_hash`` covers all question frames + url. Two snapshots with the
    same ``page_hash`` are guaranteed structurally identical for verifier
    purposes (controls + checked/value/selected state).
    """
    url: str
    frames: dict[str, QuestionFrame]  # keyed by qid
    page_hash: str
    raw_controls: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON-serializable form for AgentState storage."""
        return {
            "url": self.url,
            "page_hash": self.page_hash,
            "frames": {qid: f.to_dict() for qid, f in self.frames.items()},
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SnapshotV2 | None":
        if not data:
            return None
        frames = {
            qid: QuestionFrame(qid=f["qid"], controls=f["controls"], subtree_hash=f["subtree_hash"])
            for qid, f in data.get("frames", {}).items()
        }
        return cls(url=data["url"], frames=frames, page_hash=data["page_hash"])

    def frame(self, qid: str) -> QuestionFrame | None:
        return self.frames.get(qid)

    def diff_hashes(self, other: "SnapshotV2") -> set[str]:
        """Return qids whose subtree_hash changed (or appeared/disappeared)."""
        qids = set(self.frames) | set(other.frames)
        return {
            qid for qid in qids
            if (self.frames.get(qid).subtree_hash if self.frames.get(qid) else None)
            != (other.frames.get(qid).subtree_hash if other.frames.get(qid) else None)
        }


def _hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _build_frames(controls: list[dict]) -> dict[str, QuestionFrame]:
    by_qid: dict[str, list[dict]] = {}
    for c in controls:
        qid = c.get("qid") or ""
        by_qid.setdefault(qid, []).append(c)

    frames: dict[str, QuestionFrame] = {}
    for qid, group in by_qid.items():
        if not qid:
            continue  # orphan controls (no question container) — excluded from per-question hash
        # Sort for determinism (DOM order can shift)
        group_sorted = sorted(group, key=lambda c: (c.get("name", ""), c.get("value") or "", c.get("tag", "")))
        # Drop volatile fields from the hash input (visibility can flicker)
        hash_input = [
            {k: v for k, v in c.items() if k not in ("visible",)}
            for c in group_sorted
        ]
        frames[qid] = QuestionFrame(
            qid=qid,
            controls=group_sorted,
            subtree_hash=_hash(hash_input),
        )
    return frames


async def capture(driver: _DriverProto) -> SnapshotV2:
    """
    Single-round-trip DOM snapshot. Raises if the driver fails — caller
    decides whether to treat that as ``dom_unstable`` (verifier does).
    """
    raw = await driver.evaluate(_SNAPSHOT_JS)
    if raw is None:
        raise RuntimeError("snapshot_v2: driver.evaluate returned None")
    url = raw.get("url", "") if isinstance(raw, dict) else ""
    controls = raw.get("controls", []) if isinstance(raw, dict) else []
    frames = _build_frames(controls)
    page_hash = _hash({
        "url": url,
        "frames": sorted((qid, f.subtree_hash) for qid, f in frames.items()),
    })
    return SnapshotV2(url=url, frames=frames, page_hash=page_hash, raw_controls=controls)


def from_controls(url: str, controls: list[dict]) -> SnapshotV2:
    """Synchronous constructor for tests / replay (no driver)."""
    frames = _build_frames(controls)
    page_hash = _hash({
        "url": url,
        "frames": sorted((qid, f.subtree_hash) for qid, f in frames.items()),
    })
    return SnapshotV2(url=url, frames=frames, page_hash=page_hash, raw_controls=controls)


__all__ = ["SnapshotV2", "QuestionFrame", "capture", "from_controls"]
