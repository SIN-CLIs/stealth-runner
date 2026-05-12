"""================================================================================
COMPACT DOM SNAPSHOT — @eN Token-Efficient Element Extraction
================================================================================

WAS IST DAS?
  Erzeugt kompakte DOM-Snapshots mit @eN Referenzen aus einer Webseite.
  Nutzt CDP Runtime.evaluate im Browser (nicht cua-driver).

  UNTERscheidet sich von src/stealth_survey/compact_snapshot.py:
  - Diese Datei: Survey-CLI-Version (für survey.py)
  - src/stealth_survey/compact_snapshot.py: NEMO-Version (für run_survey.py)
  → BEIDE erfüllen denselben Zweck, aber für verschiedene Entry Points.

ARCHITEKTUR:
  ┌─────────────────────┐
  │  snapshot()         │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  CDP WebSocket      │
  │  Runtime.evaluate   │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  ELEMENT_EXTRACTOR_JS│
  │  (im Browser)       │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  Modal Detection    │
  │  (topmost overlay)  │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  CompactSnapshot    │
  │  {@e0, @e1, ...}   │
  └─────────────────────┘

WARUM Modal Detection?
  HeyPiggy Dashboard hat OVERLAYS (Survey-Preview, Account-Setup,
  Rating-Prompt). Wir müssen das TOPMOST Modal finden.
  → Strategie: Element dessen Center am nähesten zum Viewport-Center ist.
  → Hintergrund-Modals (Rating) sind oft seitlich/verschoben.

WARUM @eN Referenzen?
  - Kurz: @e0 = 3 Zeichen (vs. CSS-Selektor = 50+ Zeichen)
  - Stabil: Pro Seite eindeutig (vs. cua-driver Index = instabil)
  - LLM-freundlich: Weniger Tokens = mehr Kontext für Fragen

DEPENDENZEN:
  - .scanner (Provider Detection)
  - websocket-client (pip install websocket-client)
  - CDP WebSocket Verbindung

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

import json
import time
import websocket
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from .scanner import detect_provider


@dataclass
class CompactSnapshot:
    """Compact DOM snapshot for LLM consumption — 100% element capture (2026-05-11).

    Captures:
    - All form elements (input, button, select, textarea) via EXTRACTOR_JS
    - Shadow DOM traversal (pierces shadow roots recursively)
    - Angular CDK drag-drop puzzle (.cdk-drag, .drop-zone, img[alt])
    - HeyPiggy modal buttons (.modal-button-positive)
    - Visual captchas (canvas, img with captcha classes)
    - Images (src, alt, index) for captcha analysis
    - Iframe content (HeyPiggy embeds surveys in iframes)
    - Cookie consent banner detection
    - Provider-specific selectors (Qualtrics, Toluna, PureSpectrum)
    """
    refs: Dict[str, Dict] = field(default_factory=dict)
    semantic: Dict[str, Any] = field(default_factory=dict)
    images: List[Dict] = field(default_factory=list)  # [{type, alt, src, index, isCaptcha}]
    dragPuzzle: Optional[Dict] = None  # {type, target, dropZoneClass, dragImages, puzzleText}
    captchas: List[Dict] = field(default_factory=list)  # [{type, width, height, index}]
    progressText: str = ""
    cookieConsentBtn: Optional[Dict] = None  # {text, className}
    hasShadowDOM: bool = False
    iframeCount: int = 0
    url: str = ""
    title: str = ""
    provider: str = "unknown"
    timestamp: str = ""
    modal_center: Optional[float] = None  # dist to viewport center, null = no modal

    def to_dict(self) -> Dict:
        d = asdict(self)
        # Serialize optional fields safely
        if d.get("dragPuzzle") is None:
            d["dragPuzzle"] = None
        if d.get("cookieConsentBtn") is None:
            d["cookieConsentBtn"] = None
        return d


# ── JS Element Extractor ───────────────────────────────

# COMPREHENSIVE 2026-05-11 — 100% Element Capture
# Features:
# - Modal detection via viewport-center proximity
# - Shadow DOM traversal (pierce shadow roots recursively)
# - Angular CDK drag-drop puzzle detection (.cdk-drag, .drop-zone, img[alt])
# - HeyPiggy modal buttons (.modal-button-positive)
# - Visual captcha detection (canvas, img with captcha classes)
# - Images for captcha analysis (src, alt, index)
# - All standard form elements (input, button, select, textarea)
# - Provider-specific selectors (Qualtrics, Toluna, PureSpectrum)
# - Iframe content extraction
# - Sort by Y-position (questions before answers)
ELEMENT_EXTRACTOR_JS = r'''
(function(){
    var out = [];
    var seen = new Set();
    var images = [];
    var dragPuzzle = null;
    var captchas = [];

    // ── Shadow DOM Traversal ─────────────────────────────────────────
    // WHY: PureSpectrum and other Angular apps use shadow DOM.
    // Elements inside shadow roots are INVISIBLE to normal querySelectorAll.
    // FIX: Walk shadowRoot property recursively to find all elements.
    function walkShadows(root, depth) {
        if (!root || depth > 5) return;
        try {
            var children = root.querySelectorAll ? root.querySelectorAll('*') : [];
            for (var i = 0; i < children.length; i++) {
                var el = children[i];
                if (el.shadowRoot) {
                    walkShadows(el.shadowRoot, depth + 1);
                }
            }
            // Also scan direct children of shadow root
            var allEls = root.querySelectorAll ? root.querySelectorAll('*') : [];
            for (var j = 0; j < allEls.length; j++) {
                processEl(allEls[j]);
            }
        } catch(e) {}
    }

    // ── Modal Detection ──────────────────────────────────────────────
    function getCenter(el) {
        var r = el.getBoundingClientRect();
        if (!r || r.width === 0 || r.height === 0) return null;
        return {x: r.left + r.width/2, y: r.top + r.height/2};
    }
    function distToCenter(c) {
        var vw = window.innerWidth, vh = window.innerHeight;
        var vc = {x: vw/2, y: vh/2};
        return Math.sqrt((c.x-vc.x)*(c.x-vc.x) + (c.y-vc.y)*(c.y-vc.y));
    }

    var modalCandidates = Array.from(document.querySelectorAll(
        '[class*=modal], [role=dialog], .overlay, .dialog, .modal.show, .modal-content'
    ));
    var topModal = null;
    var bestDist = Infinity;
    modalCandidates.forEach(function(m) {
        var s = window.getComputedStyle(m);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        var c = getCenter(m);
        if (!c) return;
        var d = distToCenter(c);
        if (d < bestDist) { bestDist = d; topModal = m; }
    });

    var scanRoot = topModal || document.body;

    // ── processEl: Single element processor ─────────────────────────
    function processEl(el) {
        if (!el || seen.has(el)) return;

        var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
        var visible = rect && rect.width > 0 && rect.height > 0;
        var tag = el.tagName ? el.tagName.toLowerCase() : '';
        var text = (el.innerText || el.textContent || el.value || '').substring(0, 80).trim();

        // ══ BUTTONS ══════════════════════════════════════════════════
        if (tag === 'button' || el.type === 'submit' || el.type === 'button') {
            seen.add(el);
            var info = {
                role: 'button',
                tag: tag, text: text,
                label: (el.getAttribute('aria-label') || '').substring(0, 80),
                name: (el.getAttribute('name') || '').substring(0, 60),
                value: el.value || '', type: el.type || 'submit',
                enabled: !el.disabled && visible,
                inModal: !!topModal,
                y: rect ? Math.round(rect.y) : 0,
                className: el.className || '',
                onclick: (el.getAttribute('onclick') || '').substring(0, 100),
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // ══ HeyPiggy Modal Buttons (.modal-button-positive) ══════════
        if (el.classList && (
            el.classList.contains('modal-button-positive') ||
            el.classList.contains('modal-button-negative') ||
            el.className.includes('modal-')
        )) {
            if (el.offsetWidth > 0 && el.offsetHeight > 0 && !seen.has(el)) {
                seen.add(el);
                var isPositive = el.classList.contains('modal-button-positive');
                var info = {
                    role: isPositive ? 'button-primary' : 'button-secondary',
                    tag: tag, text: text,
                    label: (el.getAttribute('aria-label') || '').substring(0, 80),
                    name: '', value: '',
                    enabled: !el.disabled && visible,
                    inModal: true, y: rect ? Math.round(rect.y) : 0,
                    className: el.className || '',
                    onclick: (el.getAttribute('onclick') || '').substring(0, 100),
                    disabled: el.disabled || false,
                };
                out.push(info);
            }
        }

        // ══ RADIO BUTTONS ════════════════════════════════════════════
        if (el.type === 'radio') {
            seen.add(el);
            var info = {
                role: el.checked ? 'radio-selected' : 'radio',
                tag: tag, text: text,
                label: (el.getAttribute('aria-label') || el.labels && el.labels[0] ? el.labels[0].textContent : '').substring(0, 80),
                name: el.name || '',
                value: el.value || '',
                type: 'radio',
                enabled: !el.disabled && visible,
                inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // TolunaStart custom radio (div.cdk-drag with cf-radio-answer class)
        if (el.classList && el.classList.contains('cf-radio-answer')) {
            var inp = el.querySelector('input[type=radio]');
            if (inp && !seen.has(inp)) {
                seen.add(inp); seen.add(el);
                var info = {
                    role: inp.checked ? 'radio-selected' : 'radio',
                    tag: 'div', text: text,
                    label: '', name: inp.name || '', value: inp.value || '',
                    type: 'radio',
                    enabled: !inp.disabled && visible,
                    inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                };
                out.push(info);
            }
        }

        // ══ CHECKBOXES ════════════════════════════════════════════════
        if (el.type === 'checkbox') {
            seen.add(el);
            var info = {
                role: el.checked ? 'checkbox-checked' : 'checkbox',
                tag: tag, text: text,
                label: (el.getAttribute('aria-label') || el.labels && el.labels[0] ? el.labels[0].textContent : '').substring(0, 80),
                name: el.name || '',
                value: el.value || '',
                type: 'checkbox',
                enabled: !el.disabled && visible,
                inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // ══ TEXT INPUTS ═══════════════════════════════════════════════
        if (tag === 'input' && (
            el.type === 'text' || el.type === 'number' || el.type === 'email' ||
            el.type === 'tel' || el.type === 'password' || el.type === 'search' ||
            !el.type || el.type === ''
        )) {
            seen.add(el);
            var info = {
                role: 'textbox',
                tag: tag, text: text,
                label: (el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').substring(0, 80),
                name: el.name || '',
                value: (el.value || '').substring(0, 200),
                type: el.type || 'text',
                enabled: !el.disabled && visible,
                inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // ══ TEXTAREAS ═════════════════════════════════════════════════
        if (tag === 'textarea' && !el.classList.contains('g-recaptcha-response')) {
            seen.add(el);
            var info = {
                role: 'textbox',
                tag: tag, text: text,
                label: (el.getAttribute('placeholder') || '').substring(0, 80),
                name: el.name || '',
                value: (el.value || '').substring(0, 200),
                type: 'textarea',
                enabled: !el.disabled && visible,
                inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // ══ SELECTS ══════════════════════════════════════════════════
        if (tag === 'select') {
            seen.add(el);
            var opts = [];
            var options = el.querySelectorAll('option');
            for (var k = 0; k < options.length; k++) {
                opts.push({text: (options[k].textContent || '').trim().substring(0, 80), value: options[k].value || '', selected: options[k].selected});
            }
            var info = {
                role: 'select',
                tag: tag, text: text,
                label: (el.getAttribute('aria-label') || '').substring(0, 80),
                name: el.name || '',
                options: opts,
                selectedIndex: el.selectedIndex,
                type: 'select',
                enabled: !el.disabled && visible,
                inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                disabled: el.disabled || false,
            };
            out.push(info);
            return;
        }

        // ══ QUALTRICS LABELWRAPPER / CHOICESTRUCTURE ═════════════════
        if (el.classList && (
            el.classList.contains('LabelWrapper') ||
            el.classList.contains('ChoiceStructure') ||
            el.classList.contains('ChoiceRow') ||
            el.classList.contains('ChoiceBody')
        )) {
            var inp = el.querySelector('input[type=radio], input[type=checkbox]');
            if (inp && !seen.has(inp)) {
                seen.add(inp);
                var info = {
                    role: inp.checked ? 'radio-selected' : 'radio',
                    tag: tag, text: (el.textContent || '').trim().substring(0, 80),
                    label: '', name: inp.name || '', value: inp.value || '',
                    type: inp.type || 'radio',
                    enabled: !inp.disabled && visible,
                    inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                    disabled: inp.disabled || false,
                };
                out.push(info);
            }
        }

        // ══ QUESTION LABELS ═══════════════════════════════════════════
        if (tag === 'label' || tag === 'legend' || el.classList && (
            el.classList.contains('QuestionText') ||
            el.classList.contains('question-text') ||
            el.classList.contains('ScreeningQuestion')
        )) {
            var t = (el.innerText || el.textContent || '').trim();
            if (t && t.length > 3 && t.length < 300 && !seen.has(el)) {
                seen.add(el);
                out.push({
                    role: 'label', tag: tag, text: t,
                    label: '', name: '', value: '', type: '',
                    enabled: true, inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                });
            }
        }

        // ══ ANGULAR CDK DRAG-DROP PUZZLE ═══════════════════════════════
        // Detect "Zahl X in Kästchen" puzzle — PureSpectrum drag-drop captcha
        // Structure: .cdk-drop-list with .cdk-drag children (img[alt="52"])
        // Target: .drop-zone (empty box where image must be dropped)
        if (el.classList && (
            el.classList.contains('drop-zone') ||
            el.classList.contains('cdk-drop-list') ||
            el.classList.contains('cdk-drag')
        )) {
            if (!seen.has(el)) {
                seen.add(el);
                var info = {
                    role: 'drag-target',
                    tag: tag, text: text,
                    label: '', name: '', value: '', type: '',
                    enabled: visible, inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                    className: el.className || '',
                };
                out.push(info);

                // Extract draggable images (numbers like 06, 10, 52)
                var imgs = el.querySelectorAll('img[alt]');
                imgs.forEach(function(img) {
                    var alt = img.getAttribute('alt') || '';
                    if (!seen.has(img)) {
                        seen.add(img);
                        var irect = img.getBoundingClientRect ? img.getBoundingClientRect() : null;
                        out.push({
                            role: 'drag-image',
                            tag: 'img', text: alt,
                            label: '', name: '', value: '',
                            alt: alt,
                            type: 'drag-item',
                            enabled: irect && irect.width > 0,
                            inModal: !!topModal,
                            y: irect ? Math.round(irect.y) : 0,
                            className: img.className || '',
                            src: (img.src || '').substring(0, 200),
                        });
                        images.push({
                            type: 'drag-number',
                            alt: alt,
                            src: img.src ? img.src.substring(0, 200) : '',
                            index: images.length,
                        });
                    }
                });

                // Build drag puzzle info if we found draggable images
                if (dragPuzzle === null && el.classList.contains('drop-zone')) {
                    var puzzleText = text;
                    var parentText = (el.closest('.survey-question') || el.parentElement || {}).textContent || '';
                    var allText = puzzleText + ' ' + parentText;
                    // Extract number from text like "Bitte legen Sie die Zahl 52 in das leere Kästchen"
                    var numMatch = allText.match(/zahl\s*(\d+)|(\d+)\s*(?:in|into)/i);
                    var targetNum = numMatch ? (numMatch[1] || numMatch[2]) : null;
                    if (targetNum) {
                        dragPuzzle = {
                            type: 'angular-cdk-drag-drop',
                            target: targetNum,
                            dropZoneClass: 'drop-zone',
                            hasDropZone: true,
                            dragImages: Array.from(imgs).map(function(img) { return img.getAttribute('alt') || ''; }),
                            puzzleText: allText.substring(0, 200),
                        };
                    }
                }
            }
        }

        // ══ IMAGES (for captcha analysis) ══════════════════════════════
        if (tag === 'img' && visible && el.offsetWidth > 10 && el.offsetHeight > 10) {
            var alt = el.getAttribute('alt') || '';
            var src = el.src || '';
            var cls = el.className || '';
            var isCaptcha = (
                cls.includes('captcha') || cls.includes('challenge') ||
                cls.includes('captcha') || alt.includes('captcha') ||
                cls.includes('cf-image') || cls.includes('NxtBtn') ||
                alt.match(/^\d{3,6}$/)  // PureSpectrum visual captcha text (Q3333S style)
            );
            if (!seen.has(el)) {
                seen.add(el);
                out.push({
                    role: 'image', tag: 'img', text: alt,
                    label: '', name: '', value: '', type: '',
                    alt: alt, src: src.substring(0, 200),
                    enabled: visible, inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                    className: cls,
                });
            }
            images.push({
                type: isCaptcha ? 'captcha' : 'content',
                alt: alt, src: src.substring(0, 200),
                index: images.length,
                isCaptcha: isCaptcha,
                width: rect ? Math.round(rect.width) : 0,
                height: rect ? Math.round(rect.height) : 0,
            });
        }

        // ══ CANVAS (for base64 captcha / drawing captchas) ═════════════
        if (tag === 'canvas' && visible && el.offsetWidth > 20 && el.offsetHeight > 20) {
            if (!seen.has(el)) {
                seen.add(el);
                out.push({
                    role: 'canvas', tag: 'canvas', text: '',
                    label: (el.getAttribute('aria-label') || '').substring(0, 80),
                    name: '', value: '', type: '',
                    enabled: visible, inModal: !!topModal, y: rect ? Math.round(rect.y) : 0,
                    className: el.className || '',
                });
            }
            captchas.push({
                type: 'canvas',
                width: rect ? Math.round(rect.width) : 0,
                height: rect ? Math.round(rect.height) : 0,
                index: images.length,
            });
        }

        // ══ FORWARD/NEXT BUTTONS (Qualtrics, Strat7, PureSpectrum) ═══
        if (!seen.has(el) && el.offsetWidth > 0 && el.offsetHeight > 0) {
            var t = (el.textContent || '').trim();
            var cls = el.className || '';
            if (
                cls.includes('NextButton') || cls.includes('NxtBtn') ||
                cls.includes('bsbutton') || cls.includes('ForwardBtn') ||
                cls.includes('NavigationButton') ||
                t === '>>' || t === '>' || t === 'Weiter' ||
                t === 'Nächster' || t === 'Nächste' ||
                t === 'Next' || t === 'Submit' || t === 'Fortfahren' ||
                t === 'Weiters' || t === 'Send' ||
                cls.includes('choice') && t.length < 5  // Single-char buttons
            ) {
                addSimple(el, 'button');
            }
        }
    }

    // Simple add without double-processing
    function addSimple(el, role) {
        if (!el || seen.has(el)) return;
        seen.add(el);
        var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
        var visible = rect && rect.width > 0 && rect.height > 0;
        var info = {
            role: role,
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            text: (el.innerText || el.textContent || el.value || '').substring(0, 80).trim(),
            label: (el.getAttribute('aria-label') || '').substring(0, 80),
            name: (el.getAttribute('name') || '').substring(0, 60),
            value: el.value || '', type: el.type || '',
            enabled: !el.disabled && visible,
            inModal: !!topModal,
            y: rect ? Math.round(rect.y) : 0,
            className: el.className || '',
            onclick: (el.getAttribute('onclick') || '').substring(0, 100),
            disabled: el.disabled || false,
        };
        out.push(info);
    }

    // ══ MAIN SCAN: Walk all elements in scanRoot ════════════════════
    var allEls = scanRoot.querySelectorAll
        ? scanRoot.querySelectorAll('*')
        : (scanRoot.querySelectorAll ? scanRoot.querySelectorAll('*') : []);
    for (var i = 0; i < allEls.length; i++) {
        processEl(allEls[i]);
    }

    // ══ SHADOW DOM: Walk shadow roots ═══════════════════════════════
    // Walk shadow DOM of all elements in document body (not just scanRoot)
    // because shadow hosts might be outside the modal
    var allDocEls = document.querySelectorAll ? document.querySelectorAll('*') : [];
    for (var j = 0; j < allDocEls.length; j++) {
        var host = allDocEls[j];
        if (host.shadowRoot) {
            walkShadows(host.shadowRoot, 1);
        }
        // Also check for open shadow roots directly
        if (host.shadowRoot && !seen.has(host.shadowRoot)) {
            var shadowEls = host.shadowRoot.querySelectorAll ? host.shadowRoot.querySelectorAll('*') : [];
            for (var k = 0; k < shadowEls.length; k++) {
                processEl(shadowEls[k]);
            }
        }
    }

    // ══ IFRAME CONTENT (HeyPiggy embeds surveys in iframes) ═══════════
    var iframes = scanRoot.querySelectorAll ? scanRoot.querySelectorAll('iframe') : [];
    for (var fi = 0; fi < iframes.length; fi++) {
        var iframe = iframes[fi];
        var rect = iframe.getBoundingClientRect ? iframe.getBoundingClientRect() : null;
        var visible = rect && rect.width > 0 && rect.height > 0;
        if (visible && !seen.has(iframe)) {
            seen.add(iframe);
            out.push({
                role: 'iframe',
                tag: 'iframe',
                text: iframe.src || '',
                label: '', name: '', value: '', type: '',
                src: (iframe.src || '').substring(0, 300),
                enabled: visible, inModal: !!topModal,
                y: rect ? Math.round(rect.y) : 0,
                width: rect ? Math.round(rect.width) : 0,
                height: rect ? Math.round(rect.height) : 0,
            });
        }
    }

    // ══ PROGRESS BAR DETECTION ═══════════════════════════════════════
    var progressEls = document.querySelectorAll('[class*=progress], [class*=Progression]');
    var progressText = '';
    for (var pi = 0; pi < progressEls.length; pi++) {
        var pEl = progressEls[pi];
        var s = window.getComputedStyle(pEl);
        if (s.display !== 'none' && pEl.textContent) {
            var t = pEl.textContent.trim();
            if (t.match(/\d+\/\d+|%\d+|\d+%|Seite \d+/)) {
                progressText = t;
                break;
            }
        }
    }

    // ══ COOKIE CONSENT BANNER ════════════════════════════════════════
    var cookieBtn = null;
    document.querySelectorAll('[class*=cookie], #cookie, .cky-btn, .cky-btn-accept').forEach(function(cb) {
        var t = (cb.textContent || '').trim().toLowerCase();
        if (t.includes('akzeptieren') || t.includes('accept') || t.includes('alle')) {
            cookieBtn = {
                text: (cb.textContent || '').trim(),
                className: cb.className || '',
            };
        }
    });

    // ══ FINALIZE ════════════════════════════════════════════════════
    // Sort by Y position (top-to-bottom = questions before answers)
    out.sort(function(a, b) { return (a.y || 0) - (b.y || 0); });

    return JSON.stringify({
        elements: out,
        modalCenter: bestDist === Infinity ? null : bestDist,
        images: images,
        dragPuzzle: dragPuzzle,
        captchas: captchas,
        progressText: progressText,
        cookieConsentBtn: cookieBtn,
        hasShadowDOM: document.querySelectorAll('[shadow]').length > 0 || Array.from(document.querySelectorAll('*')).some(function(el) { return !!el.shadowRoot; }),
        iframeCount: iframes.length,
    });
})()
'''


# ── Generator ──────────────────────────────────────────

def generate_snapshot(ws_url, include_semantic=True):
    """Generate compact snapshot from CDP WebSocket URL.

    Args:
        ws_url: CDP WebSocket debugger URL
        include_semantic: Whether to extract semantic info

    Returns:
        CompactSnapshot with @eN refs
    """
    ws = websocket.create_connection(ws_url, timeout=15)

    # Get page metadata
    ws.send(json.dumps({
        "id": 0, "method": "Runtime.evaluate",
        "params": {
            "expression": "(function(){return JSON.stringify({url:document.location.href,title:document.title,innerText:document.body.innerText.substring(0,500)});})()"  # noqa: E501
        }
    }))
    r = json.loads(ws.recv())
    meta = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))

    # Extract elements
    ws.send(json.dumps({
        "id": 1, "method": "Runtime.evaluate",
        "params": {"expression": ELEMENT_EXTRACTOR_JS}
    }))
    r2 = json.loads(ws.recv())
    ws.close()

    # New format (2026-05-11): {elements, modalCenter, images, dragPuzzle, captchas, progressText, cookieConsentBtn, hasShadowDOM, iframeCount}  # noqa: E501
    # Legacy format: [...] (plain list, old tests) or "[]" (string)
    raw_val = r2.get("result", {}).get("result", {}).get("value", '{"elements":[]}')
    parsed = json.loads(raw_val)
    if isinstance(parsed, list):
        raw_elements = parsed
        modal_center = None
        images = []
        drag_puzzle = None
        captchas = []
        progress_text = ""
        cookie_btn = None
        has_shadow_dom = False
        iframe_count = 0
    elif isinstance(parsed, dict):
        raw_elements = parsed.get("elements", [])
        modal_center = parsed.get("modalCenter")
        images = parsed.get("images", [])
        drag_puzzle = parsed.get("dragPuzzle")
        captchas = parsed.get("captchas", [])
        progress_text = parsed.get("progressText", "")
        cookie_btn = parsed.get("cookieConsentBtn")
        has_shadow_dom = parsed.get("hasShadowDOM", False)
        iframe_count = parsed.get("iframeCount", 0)
    else:
        raw_elements = []
        modal_center = None
        images = []
        drag_puzzle = None
        captchas = []
        progress_text = ""
        cookie_btn = None
        has_shadow_dom = False
        iframe_count = 0

    # Build @eN refs — include ALL properties (role, text, label, etc.)
    refs = {}
    for i, el in enumerate(raw_elements):
        refs[f"@e{i}"] = {
            "role": el.get("role", "unknown"),
            "text": el.get("text", ""),
            "label": el.get("label", ""),
            "name": el.get("name", ""),
            "tag": el.get("tag", ""),
            "type": el.get("type", ""),
            "value": el.get("value", ""),
            "enabled": el.get("enabled", True),
            "inModal": el.get("inModal", False),
            "alt": el.get("alt", ""),
            "src": el.get("src", ""),
            "className": el.get("className", ""),
            "onclick": el.get("onclick", ""),
            "disabled": el.get("disabled", False),
            "options": el.get("options", []),
            "selectedIndex": el.get("selectedIndex", 0),
            "y": el.get("y", 0),
        }

    # Semantic info — enhanced with new capture fields
    semantic = {}
    if include_semantic:
        semantic["questions"] = _detect_questions(raw_elements)
        semantic["progress"] = progress_text or _detect_progress(raw_elements)
        semantic["buttons"] = [
            e.get("text") for e in raw_elements
            if e.get("role") in ("button", "button-primary", "button-secondary") and e.get("text")
        ][:10]
        semantic["in_page_modal"] = modal_center is not None
        semantic["dragPuzzle"] = drag_puzzle  # Angular CDK puzzle if present
        semantic["hasCaptcha"] = any(c.get("type") in ("captcha", "canvas") for c in images)
        semantic["captchaCount"] = len([c for c in images if c.get("isCaptcha")])
        semantic["cookieConsent"] = cookie_btn is not None
        semantic["hasShadowDOM"] = has_shadow_dom
        semantic["iframeCount"] = iframe_count

    url = meta.get("url", "")
    provider = detect_provider(url)
    # In-page modal: URL is always dashboard, provider unknown until survey starts
    if modal_center is not None and provider == "heypiggy":
        provider = "in_page_modal"

    return CompactSnapshot(
        refs=refs,
        semantic=semantic,
        images=images,
        dragPuzzle=drag_puzzle,
        captchas=captchas,
        progressText=progress_text,
        cookieConsentBtn=cookie_btn,
        hasShadowDOM=has_shadow_dom,
        iframeCount=iframe_count,
        url=url,
        title=meta.get("title", ""),
        provider=provider,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        modal_center=modal_center,
    )


# ── Helpers ────────────────────────────────────────────

def _detect_questions(elements):
    """Extract question texts."""
    questions = []
    for el in elements:
        if el.get("role") == "label":
            text = el.get("text", "").strip()
            if text and len(text) > 5 and "powered by" not in text.lower():
                questions.append(text)
    return questions


def _detect_progress(elements):
    """Detect survey progress."""
    for el in elements:
        text = el.get("text", "")
        if "%" in text and any(c.isdigit() for c in text):
            return text.strip()
    return "?"


def detect_completion(text):
    """SOTA: Check if survey is completed based on page text.

    Provider-specific completion patterns (2026-05-06):
    - German surveys: heypiggy, Samplicio DE
    - English surveys: Qualtrics, Toluna, Cint, PureSpectrum
    - All major panel providers covered
    """
    text_lower = text.lower()

    # ✅ SURVEY COMPLETED — all providers
    completion_markers = [
        # German
        "zurück zur website", "zurück zur umfrage", "gutgeschrieben",
        "guthaben wurde", "vielen dank", "danke für", "umfrage beendet",
        "abgeschlossen", "erfolgreich", "ausgefüllt",
        # English (Qualtrics, Toluna, Cint, PureSpectrum, Samplicio)
        "thank you for completing", "thank you for your",
        "survey complete", "completed the survey", "successfully submitted",
        "your response has been recorded", "you have completed",
        "points have been credited", "points credited", "reward credited",
        "thank you for participating", "thanks for completing",
        "your submission", "submitted successfully",
        "finished", "complete!", "completed!",
        # Progress/checking
        "finished checking", "survey has ended",
    ]
    for m in completion_markers:
        if m in text_lower:
            return True

    return False


def detect_progress(text: str) -> Tuple[bool, str]:
    """SOTA: Detect survey progress state.

    Returns (progressed, status):
    - ('advanced', 'progressed') = page advanced to next question
    - ('stuck', reason) = page is stuck or regressed
    - ('loading', 'loading') = page still loading
    - ('error', 'error_page') = error screen-out page
    - ('captcha', 'captcha') = captcha detected
    """
    text_lower = text.lower()

    # Check for error pages first
    error_markers = [
        "screen out", "you do not qualify", "not eligible",
        "no app id was specified", "unable to start survey",
        "survey has ended", "survey closed", "link expired",
        "leider ist ein fehler", "error occurred",
        "thank you for your interest",
    ]
    for m in error_markers:
        if m in text_lower:
            return False, "error_page"

    # Loading indicators
    loading_markers = ["loading", "just getting things ready", "won't be long",
                       "bitte warten", "wird geladen", "please wait"]
    for m in loading_markers:
        if m in text_lower:
            return False, "loading"

    # Captcha
    captcha_markers = ["captcha", "ich bin kein roboter", "i am not a robot",
                       "not a robot", "human check", "human verification"]
    for m in captcha_markers:
        if m in text_lower:
            return False, "captcha"

    # Progress bar (common in Qualtrics, Cint)
    progress_patterns = [
        r"(\d+)\s*/\s*\d+",  # "3/10" progress
        r"fortschritt.*?(\d+)%",  # German progress
        r"progress.*?(\d+)%",
        r"[████░░░░▓▓▒]",
    ]
    for pat in progress_patterns:
        if re.search(pat, text_lower):
            return True, "progressed"

    # Question indicators (page advanced)
    question_markers = [
        "wie", "was", "wann", "warum",  # German question words
        "how often", "how many", "do you", "would you", "please select",
        "bitte auswählen", "stimmen sie zu", "meinungen",
        "radio", "checkbox", "submit", "next", "weiter",
    ]
    question_count = sum(1 for m in question_markers if m in text_lower)
    if question_count >= 2:
        return True, "progressed"

    return True, "unknown"
