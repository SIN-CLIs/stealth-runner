"""Compact Snapshot Generator — Token-efficient DOM snapshots with @eN refs.

Inspired by Vercel agent-browser's compact snapshot format.
Uses CDP WebSocket to extract interactive elements from a survey page.
"""

import json
import time
import urllib.request
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class ElementRef:
    """Compact element reference for LLM consumption."""
    index: int
    role: str
    text: str = ""
    label: str = ""
    name: str = ""
    value: str = ""
    tag: str = ""
    selector_type: str = ""  # "radio", "checkbox", "text", "button", "select"
    enabled: bool = True
    bounds: Optional[Dict[str, int]] = None

    @property
    def ref(self) -> str:
        return f"@e{self.index}"

    def to_dict(self) -> Dict:
        d = {"role": self.role, "text": self.text}
        if self.label and self.label != self.text:
            d["label"] = self.label
        if self.name:
            d["name"] = self.name
        if self.value:
            d["value"] = self.value
        if self.tag:
            d["tag"] = self.tag
        if self.selector_type:
            d["type"] = self.selector_type
        if not self.enabled:
            d["enabled"] = False
        return d


@dataclass
class CompactSnapshot:
    """Complete compact snapshot of a survey page."""
    refs: Dict[str, Dict] = field(default_factory=dict)
    semantic: Dict[str, Any] = field(default_factory=dict)
    url: str = ""
    title: str = ""
    stealth_score: float = 0.0
    timestamp: str = ""
    provider: str = "unknown"

    def to_dict(self) -> Dict:
        return asdict(self)


class CompactSnapshotGenerator:
    """Generate compact DOM snapshots via CDP WebSocket.

    Extracts only interactive elements (buttons, inputs, select, textarea)
    and assigns @eN compact references for LLM consumption.
    """

    # Elements to include in the snapshot
    INTERACTIVE_SELECTORS = [
        "input[type=radio]",
        "input:not([type=radio]):not([type=hidden])",
        "textarea",
        "select",
        "button",
        "a[href]",
        ".NextButton",
        ".cf-radio",
        ".cf-checkbox",
        ".bsbutton",
        "label",
    ]

    def __init__(self, port: int = 9999):
        self.port = port
        self._base_url = f"http://127.0.0.1:{port}/json"

    def _get_tab_ws(self, tab_id: str) -> Optional[str]:
        """Get WebSocket URL for a specific tab."""
        try:
            pages = json.loads(urllib.request.urlopen(self._base_url).read())
            for p in pages:
                if p.get("id") == tab_id:
                    return p.get("webSocketDebuggerUrl")
        except Exception:
            pass
        return None

    def _get_any_dashboard_ws(self) -> Optional[str]:
        """Get WebSocket URL for any dashboard tab."""
        try:
            pages = json.loads(urllib.request.urlopen(self._base_url).read())
            for p in pages:
                if "dashboard" in p.get("url", ""):
                    return p.get("webSocketDebuggerUrl")
            # Fallback: first tab
            if pages:
                return pages[0].get("webSocketDebuggerUrl")
        except Exception:
            pass
        return None

    def generate(self, ws_url: str, include_semantic: bool = True) -> CompactSnapshot:
        """Generate a compact snapshot from a CDP WebSocket URL.

        Args:
            ws_url: CDP WebSocket URL for the survey tab
            include_semantic: Whether to include semantic grouping

        Returns:
            CompactSnapshot with @eN element refs
        """
        import websocket

        ws = websocket.create_connection(ws_url, timeout=15)

        # 1. Get page metadata
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": "(function(){return JSON.stringify({url:document.location.href,title:document.title,innerText:document.body.innerText.substring(0,500)});})()"}
        }))
        r = json.loads(ws.recv())
        meta = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))

        # 2. Get all interactive elements
        js_extract = self._build_element_extractor()
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js_extract}
        }))
        r2 = json.loads(ws.recv())
        ws.close()

        raw_elements = json.loads(
            r2.get("result", {}).get("result", {}).get("value", "[]")
        )

        # 3. Build @eN refs
        refs = {}
        for i, el in enumerate(raw_elements):
            ref = ElementRef(
                index=i,
                role=el.get("role", "unknown"),
                text=el.get("text", ""),
                label=el.get("label", ""),
                name=el.get("name", ""),
                value=el.get("value", ""),
                tag=el.get("tag", ""),
                selector_type=el.get("type", ""),
                enabled=el.get("enabled", True),
            )
            refs[ref.ref] = ref.to_dict()

        # 4. Semantic grouping
        semantic = {}
        if include_semantic:
            semantic["questions"] = self._detect_questions(raw_elements)
            semantic["progress"] = self._detect_progress(raw_elements)
            semantic["survey_type"] = self._detect_provider(meta.get("url", ""))
            semantic["buttons"] = [
                e.get("text") for e in raw_elements
                if e.get("role") == "button" and e.get("text")
            ][:5]

        # 5. Detect provider from URL
        provider = self._detect_provider(meta.get("url", ""))

        return CompactSnapshot(
            refs=refs,
            semantic=semantic,
            url=meta.get("url", ""),
            title=meta.get("title", ""),
            provider=provider,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def _build_element_extractor(self) -> str:
        """Build JavaScript to extract interactive elements."""
        return """
(function(){
    var out = [];
    var seen = new Set();

    function add(el, role) {
        if (!el || seen.has(el)) return;
        seen.add(el);

        var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
        var visible = rect && rect.width > 0 && rect.height > 0;

        var info = {
            role: role,
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            text: (el.innerText || el.textContent || el.value || '').substring(0, 80).trim(),
            label: (el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').substring(0, 80),
            name: (el.getAttribute('name') || '').substring(0, 60),
            value: el.value || '',
            type: el.type || '',
            enabled: !el.disabled && visible,
        };
        out.push(info);
    }

    // Buttons: NextButton, submit, regular buttons
    document.querySelectorAll('button, input[type=submit], input[type=button], .NextButton, .bsbutton, [role=button]').forEach(function(el) {
        add(el, 'button');
    });

    // Radio buttons
    document.querySelectorAll('input[type=radio], .cf-radio').forEach(function(el) {
        add(el, el.checked ? 'radio-selected' : 'radio');
    });

    // Checkboxes
    document.querySelectorAll('input[type=checkbox], .cf-checkbox').forEach(function(el) {
        add(el, el.checked ? 'checkbox-checked' : 'checkbox');
    });

    // Text inputs
    document.querySelectorAll('input[type=text], input[type=number], input[type=email], input:not([type])').forEach(function(el) {
        add(el, 'textbox');
    });

    // Textareas
    document.querySelectorAll('textarea').forEach(function(el) {
        if (!el.classList.contains('g-recaptcha-response')) {
            add(el, 'textbox');
        }
    });

    // Selects
    document.querySelectorAll('select').forEach(function(el) {
        add(el, 'select');
    });

    // Links
    document.querySelectorAll('a[href]').forEach(function(el) {
        var rect = el.getBoundingClientRect();
        var t = (el.innerText || '').trim();
        if (t && rect && rect.width > 20) {
            add(el, 'link');
        }
    });

    // Labels (for question text detection)
    document.querySelectorAll('label, .QuestionText, .question-text, legend').forEach(function(el) {
        var t = (el.innerText || el.textContent || '').trim();
        if (t && t.length > 3 && t.length < 200) {
            var info = {
                role: 'label',
                tag: el.tagName ? el.tagName.toLowerCase() : '',
                text: t,
                label: '',
                name: '',
                value: '',
                type: '',
                enabled: true,
            };
            out.push(info);
        }
    });

    return JSON.stringify(out);
})()
"""

    @staticmethod
    def _detect_questions(elements: List[Dict]) -> List[str]:
        """Extract question texts from elements."""
        questions = []
        for el in elements:
            if el.get("role") == "label":
                text = el.get("text", "").strip()
                if text and len(text) > 5 and "powered by" not in text.lower():
                    questions.append(text)
        return questions

    @staticmethod
    def _detect_progress(elements: List[Dict]) -> str:
        """Detect survey progress if visible."""
        for el in elements:
            text = el.get("text", "")
            if "%" in text and any(c.isdigit() for c in text):
                return text.strip()
        return "?"

    @staticmethod
    def _detect_provider(url: str) -> str:
        """Detect survey provider from URL."""
        url_lower = url.lower()
        if "qualtrics.com" in url_lower:
            return "qualtrics"
        if "tolunastart.com" in url_lower or "toluna.com" in url_lower:
            return "tolunastart"
        if "purespectrum.com" in url_lower:
            return "purespectrum"
        if "strat7audiences.com" in url_lower:
            return "strat7"
        if "brand-ambassador.com" in url_lower:
            return "brand_ambassador"
        if "insights-today.com" in url_lower:
            return "insights_today"
        if "surveyrouter.com" in url_lower:
            return "surveyrouter"
        if "surveys.com" in url_lower:
            return "gfk"
        return "unknown"
