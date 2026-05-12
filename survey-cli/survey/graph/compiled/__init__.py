"""Frozen graph snapshots, one file per promotion.

This directory is populated by ``survey.graph.promote`` when a graph
configuration has earned 10 clean runs in a row. Each file in here is:

  - Named ``survey_graph_v<TIMESTAMP>.py`` where TIMESTAMP is UTC ISO-8601.
  - A byte-for-byte copy of ``survey/graph/graph.py`` at promotion time.
  - chmod 444 (best-effort; see ``promote.compile_snapshot``).
  - Append-only — never modified after creation.

Production replays should import the specific version they want, not
the live ``graph.py``::

    from survey.graph.compiled import survey_graph_v20260512T120000Z as g
    state = g.build_graph().invoke(...)

Manual deletion of files in this directory is fine for housekeeping but
should be audited against ``logs/graph-promotions.jsonl``.

Closes #43.
"""
