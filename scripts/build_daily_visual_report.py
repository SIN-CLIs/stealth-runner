#!/usr/bin/env python3
"""scripts/build_daily_visual_report.py -- SR-173 daily aggregator (#178).

PURPOSE
=======
Per-step HTML debug reports written by `survey.observability.visual_debug`
land in:

    <VISUAL_DEBUG_OUTPUT_DIR>/YYYY-MM-DD/step-<id>.html

This script crawls one day's directory and builds:

    <VISUAL_DEBUG_OUTPUT_DIR>/YYYY-MM-DD/index.html

A grid-layout index with a thumbnail (the first <img data:image/jpeg...>
extracted from each per-step file), a status pill (OK / FAIL inferred from
the `class="pill bad|good"` attribute the renderer emits), and the click
URL for keyboard-friendly drill-down.

Optional Vercel-Blob upload: if `BLOB_READ_WRITE_TOKEN` is set we upload the
*index* (and each step file) to Vercel Blob and print the signed URL. We
deliberately do NOT upload the original full-page PNGs -- the JPEGs inside
the per-step HTML are the canonical artifact.

USAGE
=====
    # Build today's index (no upload):
    python scripts/build_daily_visual_report.py

    # Build a specific day:
    python scripts/build_daily_visual_report.py --date 2026-05-13

    # Build + upload to Vercel Blob:
    BLOB_READ_WRITE_TOKEN=vercel_blob_rw_xxx \\
        python scripts/build_daily_visual_report.py --upload

EXIT CODES
==========
    0  -- index built (possibly uploaded)
    1  -- no per-step files found for the requested date
    2  -- upload was requested but BLOB_READ_WRITE_TOKEN missing
    3  -- unexpected I/O error

BANNED METHODS -- NIEMALS VERWENDEN (see AGENTS.md for full list)
================================================================
- pkill -f "Google Chrome"   - killall Google Chrome
- webauto-nodriver           - playstealth launch
- skylight-cli click --element-index   - cua-driver click (raw index)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# We deliberately do NOT import survey.* here -- the aggregator runs as a
# standalone cron job and we want zero import-time coupling to the runner.
logger = logging.getLogger("daily_visual_report")

# Regexes pre-compiled at module load -- the renderer's output format is
# stable (see `_HTML_TEMPLATE` in visual_debug.py).
_RE_THUMB = re.compile(rb'src="(data:image/jpeg;base64,[^"]{0,200000})"', re.I)
_RE_PILL = re.compile(rb'class="pill (good|bad)">([A-Z]+)<', re.I)
_RE_URL_PILL = re.compile(rb'<span class="pill">([^<]{1,200})</span>')
_RE_STEP_ID = re.compile(r"step-(.+)\.html$")


# index template
_INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Visual Debug Index -- {date}</title>
<style>
 :root {{ --bg:#0f1115; --panel:#181b22; --fg:#e7ebf0; --muted:#8a93a3;
          --ok:#1f7a3a; --fail:#b00020; }}
 * {{ box-sizing: border-box; }}
 body {{ margin:0; background:var(--bg); color:var(--fg); font-family:ui-sans-serif,system-ui;
        font-size:13px; }}
 header {{ padding:12px 16px; border-bottom:1px solid #2a2f3a; display:flex;
           gap:12px; align-items:baseline; }}
 header h1 {{ margin:0; font-size:14px; }}
 header .meta {{ color:var(--muted); }}
 nav.filters {{ padding:8px 16px; display:flex; gap:10px; }}
 nav.filters button {{
   background:var(--panel); color:var(--fg); border:1px solid #2a2f3a;
   padding:4px 10px; border-radius:14px; font:inherit; cursor:pointer;
 }}
 nav.filters button.active {{ background:#2a3142; border-color:#3a425a; }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));
          gap:10px; padding:12px; }}
 .card {{ background:var(--panel); border-radius:6px; overflow:hidden;
          border-top:4px solid var(--muted); text-decoration:none; color:inherit;
          display:flex; flex-direction:column; }}
 .card.good {{ border-top-color:var(--ok); }}
 .card.bad  {{ border-top-color:var(--fail); }}
 .card img  {{ display:block; width:100%; height:140px; object-fit:cover;
               background:#000; }}
 .card .body {{ padding:8px 10px; font-size:11px; }}
 .card .body .id  {{ font-weight:600; }}
 .card .body .url {{ color:var(--muted); display:block; white-space:nowrap;
                     overflow:hidden; text-overflow:ellipsis; }}
</style>
</head>
<body>
<header>
  <h1>Visual Debug Index -- {date}</h1>
  <span class="meta">{count} steps -- generated {generated_at}</span>
</header>
<nav class="filters" role="tablist" aria-label="status filter">
  <button class="active" data-filter="all">All ({count})</button>
  <button data-filter="good">OK ({n_ok})</button>
  <button data-filter="bad">FAIL ({n_fail})</button>
</nav>
<div class="grid" id="grid">
{cards}
</div>
<script>
(function () {{
  const grid = document.getElementById('grid');
  const buttons = document.querySelectorAll('nav.filters button');
  buttons.forEach(b => b.addEventListener('click', () => {{
    buttons.forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const f = b.dataset.filter;
    grid.querySelectorAll('.card').forEach(c => {{
      c.style.display = (f === 'all' || c.classList.contains(f)) ? '' : 'none';
    }});
  }}));
}})();
</script>
</body>
</html>
"""

_CARD_TEMPLATE = """  <a class="card {status}" href="{href}">
    <img alt="step thumbnail" src="{thumb}">
    <div class="body">
      <div class="id">{step_id}</div>
      <span class="url">{url_pill}</span>
    </div>
  </a>"""


def _extract_card_data(path: Path) -> dict[str, str] | None:
    """Pull thumbnail + status + url-pill out of one per-step HTML file."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    m_thumb = _RE_THUMB.search(data)
    if not m_thumb:
        # Renderer must have failed mid-write; ignore.
        return None
    m_pill = _RE_PILL.search(data)
    status = (m_pill.group(1).decode() if m_pill else "good").lower()
    m_url = _RE_URL_PILL.search(data)
    url_pill = m_url.group(1).decode() if m_url else ""
    m_id = _RE_STEP_ID.search(path.name)
    step_id = m_id.group(1) if m_id else path.stem
    return {
        "status": status,
        "thumb": m_thumb.group(1).decode(),
        "step_id": step_id,
        "url_pill": url_pill,
        "href": path.name,
    }


def _iter_step_files(day_dir: Path) -> Iterable[Path]:
    yield from sorted(day_dir.glob("step-*.html"))


def build_index(day_dir: Path) -> tuple[Path, dict[str, int]]:
    """Build `index.html` inside `day_dir` and return (path, counts)."""
    cards: list[str] = []
    counts = {"all": 0, "good": 0, "bad": 0}
    for f in _iter_step_files(day_dir):
        if f.name == "index.html":
            continue
        card = _extract_card_data(f)
        if not card:
            continue
        counts["all"] += 1
        counts[card["status"]] = counts.get(card["status"], 0) + 1
        cards.append(_CARD_TEMPLATE.format(**card))

    if counts["all"] == 0:
        raise FileNotFoundError(f"no per-step HTML files in {day_dir}")

    html = _INDEX_TEMPLATE.format(
        date=day_dir.name,
        count=counts["all"],
        n_ok=counts.get("good", 0),
        n_fail=counts.get("bad", 0),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        cards="\n".join(cards),
    )
    out = day_dir / "index.html"
    tmp = out.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, out)  # atomic
    return out, counts


# Vercel Blob upload (optional)
# We use the public HTTP API documented at https://vercel.com/docs/storage/vercel-blob
# Endpoint: `PUT https://blob.vercel-storage.com/<pathname>` with header
#   `authorization: Bearer $BLOB_READ_WRITE_TOKEN`
# Response: JSON {url: "https://...", downloadUrl: "..."}.
# We avoid the SDK to keep the script dep-free.

def _upload_to_blob(file: Path, blob_path: str, token: str) -> str:
    """Upload one file to Vercel Blob; return the public URL.

    The URL is *immutable* per upload, so naming with date+step_id gives us
    de-facto signed URLs without TTL bookkeeping. For private buckets the
    URL token in the path is the access secret.
    """
    import urllib.request

    body = file.read_bytes()
    req = urllib.request.Request(
        f"https://blob.vercel-storage.com/{blob_path}",
        method="PUT",
        data=body,
        headers={
            "authorization": f"Bearer {token}",
            "x-content-type": "text/html; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec: trusted endpoint
        payload = json.loads(resp.read())
    return payload["url"]


def upload_day(day_dir: Path, *, token: str) -> dict[str, str]:
    """Upload every HTML in day_dir; return {filename: blob_url}."""
    out: dict[str, str] = {}
    for f in sorted(day_dir.glob("*.html")):
        url = _upload_to_blob(f, f"survey-debug-{day_dir.name}/{f.name}", token)
        out[f.name] = url
    return out


# CLI
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build daily visual-debug index.")
    p.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="UTC date in YYYY-MM-DD; defaults to today (UTC).",
    )
    p.add_argument(
        "--root",
        default=os.environ.get(
            "VISUAL_DEBUG_OUTPUT_DIR",
            str(Path.cwd() / "debug-reports"),
        ),
        help="Root directory containing per-day folders. "
        "Default: $VISUAL_DEBUG_OUTPUT_DIR or ./debug-reports.",
    )
    p.add_argument(
        "--upload",
        action="store_true",
        help="Upload index + step files to Vercel Blob. Requires $BLOB_READ_WRITE_TOKEN.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args(argv)
    day_dir = Path(args.root) / args.date
    if not day_dir.is_dir():
        logger.error("day dir does not exist: %s", day_dir)
        return 1

    try:
        index_path, counts = build_index(day_dir)
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except OSError as e:  # pragma: no cover -- defensive
        logger.exception("I/O error building index: %s", e)
        return 3

    logger.info(
        "built %s -- %d steps (ok=%d, fail=%d)",
        index_path,
        counts.get("all", 0),
        counts.get("good", 0),
        counts.get("bad", 0),
    )

    if args.upload:
        token = os.environ.get("BLOB_READ_WRITE_TOKEN")
        if not token:
            logger.error("--upload requested but BLOB_READ_WRITE_TOKEN is unset")
            return 2
        urls = upload_day(day_dir, token=token)
        logger.info("uploaded %d files to Vercel Blob", len(urls))
        # Public URL of the index goes to stdout so cron jobs can capture it.
        if "index.html" in urls:
            print(urls["index.html"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
