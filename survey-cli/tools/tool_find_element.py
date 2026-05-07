"""Element Finding Tool - __frozen__=True

REGEL: NUR finden, NICHT klicken. Klick = tool_click.py.

Usage:
    from tools.tool_find_element import find_element, find_all

    el = find_element(markdown, role="AXButton", label="Weiter")
    el = find_element((pid, wid), role="AXLink", label="Google")
    elements = find_all(markdown, role="AXRadioButton")

Boundary-Match Regeln:
    - "Weiter" in "Weiter" -> match
    - "Weiter" in "Weitere Informationen" -> NO (boundary)
    - "Berlin" in "Berlin, 10785" -> match
"""

from __future__ import annotations
import re
import subprocess
import json
from typing import Dict, List, Optional, Tuple

__frozen__ = True
__version__ = "2026-05-07"
CUA_BIN = "cua-driver"


def _parse_markdown(markdown: str) -> List[Dict]:
    if not markdown or not markdown.strip():
        return []
    elements = []
    # - [42] AXButton ("Weiter") @(100,200,300,400)
    # - [42] AXButton ("Weiter")
    # - [42] AXButton   <- no text
    # - [42] AXStaticText ("Some text")
    pattern = re.compile(
        r'- \[(\d+)\]\s+(AX[\w]+)(?:\s*\(([^)]*)\))?(?:\s*@\((\d+),(\d+),(\d+),(\d+)\))?'
    )
    for match in pattern.finditer(markdown):
        idx, role = int(match.group(1)), match.group(2)
        text = match.group(3) or ""
        bounds = None
        if match.group(4):
            bounds = (int(match.group(4)), int(match.group(5)),
                      int(match.group(6)), int(match.group(7)))
        elements.append({
            "element_index": idx,
            "role": role,
            "text": text.strip(),
            "bounds": bounds,
        })
    return elements


def _get_state(pid: int, wid: int) -> str:
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "get_window_state"],
            input=json.dumps({"pid": pid, "window_id": wid}),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return ""
        data = json.loads(result.stdout)
        return data.get("tree_markdown", "")
    except Exception:
        return ""


def _boundary_match(label: str, text: str) -> bool:
    """Word-boundary exact match.

    Find label as a whole word in text.
    - Preceded by non-word char OR start of string
    - Followed by non-word char AND NOT followed by word chars
      (prevents prefix matches like "Weiter" in "Weitere")
    """
    if not label or not text:
        return False
    if label.lower() == text.lower():
        return True
    try:
        escaped = re.escape(label)
        # Negative lookahead: NOT followed by word-char
        pattern = r'\b' + escaped + r'(?!\w)'
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return False


def _text_contains(label: str, text: str) -> bool:
    if not label or not text:
        return False
    return label.lower() in text.lower()


def find_element(
    markdown_or_state,
    role: str,
    label: Optional[str] = None,
    text_sub: Optional[str] = None,
    use_boundary: bool = True,
) -> Optional[Dict]:
    """Find FIRST matching element in AX-Tree.

    Args:
        markdown_or_state: AX-Tree markdown string OR (pid, wid) tuple
        role: AXRole to match (e.g. "AXButton", "AXRadioButton", "AXTextField")
        label: Exact label text with word-boundary matching
        text_sub: Substring fallback (when label is partial match)
        use_boundary: If True, use word-boundary for label (strict).
                      If False, use substring match.

    Returns:
        {"element_index": int, "role": str, "text": str, "bounds": tuple}
        or None if not found.
    """
    if isinstance(markdown_or_state, (tuple, list)):
        pid, wid = markdown_or_state
        markdown = _get_state(pid, wid)
    else:
        markdown = markdown_or_state

    if not markdown:
        return None

    elements = _parse_markdown(markdown)
    if not elements:
        return None

    candidates = [e for e in elements if e["role"] == role]
    if not candidates:
        return None

    if not label and not text_sub:
        return candidates[0]

    for e in candidates:
        text = e["text"]
        if label:
            if use_boundary and _boundary_match(label, text):
                return e
            if not use_boundary and _text_contains(label, text):
                return e
        if text_sub and _text_contains(text_sub, text):
            return e

    # Fallback: case-insensitive exact match on full text
    for e in candidates:
        if e["text"].lower() == label.lower():
            return e

    return None


def find_all(markdown_or_state, role: str, label: Optional[str] = None,
             text_sub: Optional[str] = None) -> List[Dict]:
    """Find ALL matching elements (not just first).

    Returns:
        [{"element_index": int, "role": str, "text": str, "bounds": tuple}, ...]
        Empty list if none found.
    """
    if isinstance(markdown_or_state, (tuple, list)):
        pid, wid = markdown_or_state
        markdown = _get_state(pid, wid)
    else:
        markdown = markdown_or_state

    if not markdown:
        return []

    elements = _parse_markdown(markdown)
    if not elements:
        return []

    candidates = [e for e in elements if e["role"] == role]
    if not label and not text_sub:
        return candidates

    results = []
    for e in candidates:
        text = e["text"]
        if label and _boundary_match(label, text):
            results.append(e)
        elif text_sub and _text_contains(text_sub, text):
            results.append(e)
    return results


def find_in_window(pid: int, wid: int, role: str,
                   label: Optional[str] = None, text_sub: Optional[str] = None) -> Optional[Dict]:
    """Find element in a specific window (pid + wid)."""
    return find_element((pid, wid), role, label, text_sub)


def find_button(markdown_or_state, label: str) -> Optional[Dict]:
    """Find AXButton by label with boundary-match."""
    return find_element(markdown_or_state, "AXButton", label=label)


def find_radio(markdown_or_state, label: str) -> Optional[Dict]:
    """Find AXRadioButton by label with boundary-match."""
    return find_element(markdown_or_state, "AXRadioButton", label=label)


def find_textfield(markdown_or_state, label_sub: str) -> Optional[Dict]:
    """Find AXTextField by label substring (partial match OK)."""
    return find_element(markdown_or_state, "AXTextField", text_sub=label_sub)


def find_link(markdown_or_state, label: str) -> Optional[Dict]:
    """Find AXLink by label with boundary-match."""
    return find_element(markdown_or_state, "AXLink", label=label)


def find_checkbox(markdown_or_state, label: str) -> Optional[Dict]:
    """Find AXCheckBox by label with boundary-match."""
    return find_element(markdown_or_state, "AXCheckBox", label=label)


def diagnose(markdown_or_state, role: str, label: Optional[str] = None) -> Dict:
    """Return diagnosis info when find_element fails."""
    if isinstance(markdown_or_state, (tuple, list)):
        pid, wid = markdown_or_state
        markdown = _get_state(pid, wid)
    else:
        markdown = markdown_or_state
    elements = _parse_markdown(markdown) if markdown else []
    role_elements = [e for e in elements if e["role"] == role]
    nl = "\n"
    return {
        "elements_total": len(elements),
        "role_matches": len(role_elements),
        "role_elements": [{"idx": e["element_index"], "text": e["text"]} for e in role_elements[:10]],
        "label_requested": label,
        "markdown_lines": len(markdown.split(nl)) if markdown else 0,
    }


if __name__ == "__main__":
    md = """
- [246] AXButton ("Weiter")
- [247] AXButton ("Weitere Informationen")
- [35] AXTextField ("E-Mail oder Telefonnummer")
- [10] AXRadioButton ("Mannlich")
- [11] AXRadioButton ("Weiblich")
- [12] AXRadioButton ("Divers")
- [54] AXLink ("Google anmelden")
- [200] AXButton ("Zustimmen und fortfahren")
"""
    # Boundary tests
    # "Weiter" matches button "Weiter" exactly
    assert find_element(md, "AXButton", label="Weiter")["element_index"] == 246
    # "Weiter" does NOT match "Weitere Informationen" (different word)
    result_weiter = find_element(md, "AXButton", label="Weiter")
    assert result_weiter is None or result_weiter["element_index"] == 246, \
        f"'Weiter' should only match 'Weiter', got: {result_weiter}"
    # "Weitere" DOES match "Weitere Informationen" (complete word)
    assert find_element(md, "AXButton", label="Weitere")["element_index"] == 247

    # Substring tests
    assert find_element(md, "AXTextField", text_sub="e-mail")["element_index"] == 35
    assert find_element(md, "AXRadioButton", label="Mannlich")["element_index"] == 10
    assert find_element(md, "AXLink", label="Google anmelden")["element_index"] == 54

    # find_all
    radios = find_all(md, "AXRadioButton")
    assert len(radios) == 3

    # Special finders
    assert find_button(md, "Weiter")["element_index"] == 246
    assert find_radio(md, "Weiblich")["element_index"] == 11
    assert find_textfield(md, "E-Mail")["element_index"] == 35

    # diagnose
    diag = diagnose(md, "AXTextField", label="Password")
    assert diag["role_matches"] == 1
    assert diag["elements_total"] > 0

    print("All tests passed")