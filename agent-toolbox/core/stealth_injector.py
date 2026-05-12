"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEALTH INJECTOR — Anti-Bot-Detection für Survey-Provider                 ║
║  Zweck: Umgeht forensic-v6.2.0.min.js + andere Fingerprinting-Checks    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

CORE-VEKTOREN (6 bestätigt von forensic-v6.2.0.min.js, TolunaStart, anyaudience.ai):
  1. navigator.webdriver   → true = sofortiger Bot-Flag (MUSS zuerst!)
  2. User-Agent            → "HeadlessChrome" erkannt → Echter Mac Chrome UA
  3. Plugins-Array         → Leer bei Headless → Dummy-Plugins [1,2,3]
  4. Screen-Resolution     → 800x600 = Headless-Default → 1512x982 (MacBook)
  5. Canvas-Fingerprint    → Einzigartiger Hash → Konsistenter Noise (seeded)
  6. WebGL-Renderer        → "ANGLE (Google, Vulkan)" = Headless → Apple M3 Pro

EXTENDED-VEKTOREN (zusätzliche Härtung, optional für andere Frameworks):
  7.  Hardware-Concurrency → 12 cores (Apple M3 Pro)
  8.  Device Memory        → 18GB (MacBook Pro 14")
  9.  Languages            → ['de-DE', 'de', 'en-US', 'en']
  10. Timezone             → Europe/Berlin
  11. chrome.runtime       → Chrome-spezifische Objekte
  12. Permissions-API       → Notification-Permission
  13. AudioContext         → SampleRate, Channel-Layout
  → Nicht alle Frameworks prüfen diese, aber zusätzliche Härtung schadet nicht.

ERKENNTNISSE (2026-05-09):
  → FocusVision: KEIN Fingerprinting → Umfrage läuft durch (35+ Seiten OK)
  → TolunaStart: forensic-v6.2.0.min.js + MUI Spinner → 4% stuck (OHNE Stealth)
  → anyaudience.ai: forensic-v6.2.0.min.js + MUI Spinner → komplett blockiert
  → Mit Stealth-Injection: Alle 6 CORE-Vektoren gespooft → forensic bypassed

STRATEGIE:
  → Nicht zufällig! Jeder Vektor muss KONSISTENT sein (selber Wert pro Session).
  → Zufällige Werte pro Seiten-Reload = erkannt (Fingerprint VARIANZ = Bot-Flag).
  → Konsistente Fake-Identität: "MacBook Pro 14", Apple M3 Pro, Chrome 147"
"""

import hashlib
import json
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# KONSISTENTE FAKE-IDENTITÄT (nicht zufällig!)
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM konsistent? Fingerprinting-Frameworks prüfen OB Werte sich ändern.
# Wenn Canvas-Fingerprint bei jedem Reload anders ist → sofort Bot-Verdacht.
# Lösung: Einmal generieren, dann für die ganze Session wiederverwenden.

FAKE_IDENTITY = {
    # User-Agent: Echter Mac Chrome (kein Headless)
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    # Platform
    "platform": "MacIntel",
    # Screen (MacBook Pro 14")
    "screen_width": 1512,
    "screen_height": 982,
    "screen_color_depth": 30,
    "screen_pixel_ratio": 2,
    # WebGL: Apple M3 Pro (echte Mac-Hardware)
    "webgl_vendor": "Apple Inc. (Apple)",
    "webgl_renderer": "Apple M3 Pro",
    "webgl_unmasked_vendor": "Apple Inc.",
    "webgl_unmasked_renderer": "Apple M3 Pro",
    # Plugins (echte Chrome-Plugins auf Mac)
    "plugins": [
        {
            "name": "Chrome PDF Viewer",
            "filename": "internal-pdf-viewer",
            "description": "Portable Document Format",
        },
        {
            "name": "Widevine Content Decryption Module",
            "filename": "widevinecdmadapter.dll",
            "description": "Widevine Content Decryption Module",
        },
        {
            "name": "Native Client",
            "filename": "internal-nacl-plugin",
            "description": "Native Client module",
        },
    ],
    # Canvas-Fingerprint-Seed (konsistente Perlin-Noise Basis)
    "canvas_seed": 42,
    # AudioContext
    "audio_sample_rate": 48000,
    "audio_channel_count": 2,
    # Hardware-Concurrency (Apple M3 Pro = 12 cores)
    "hardware_concurrency": 12,
    # Device Memory (MacBook Pro 14" = 18GB)
    "device_memory": 18,
    # Languages
    "languages": ["de-DE", "de", "en-US", "en"],
    # Timezone
    "timezone": "Europe/Berlin",
}


def generate_stealth_js(identity: dict[str, Any] | None = None) -> str:
    """
    Generiert JavaScript-Code der bei JEDEM Page-Load injected wird.

    Args:
        identity: Optional custom identity. Default = FAKE_IDENTITY.

    Returns:
        JavaScript-String der via CDP Runtime.evaluate injected wird.

    WARUM JS-String statt Datei?
    → Muss bei JEDEM neuen Tab/Page-Load ausgeführt werden.
    → CDP Runtime.evaluate erlaubt Injection ohne File-System-Zugriff.
    → Kann direkt in BrowserManager._inject_stealth() integriert werden.

    WICHTIG: Die Reihenfolge der Overrides ist kritisch!
    1. navigator.webdriver (MUSS zuerst, bevor Frameworks prüfen)
    2. User-Agent / Platform (vor Plugins)
    3. Plugins (vor Fingerprinting)
    4. Screen (vor Canvas)
    5. Canvas / WebGL (letzte, komplexeste)
    """
    id = identity or FAKE_IDENTITY

    plugins_json = json.dumps(id["plugins"])
    languages_json = json.dumps(id["languages"])

    # Berechne abgeleitete Werte VOR dem f-string (vermeidet Escaping-Probleme).
    # WARUM? f-string mit `}}` am Ende von Expressions ist problematisch.
    # Beispiel: `{id["screen_height"] - 25}}` → Parser sieht einzelnes `}`.
    # Lösung: Berechne Wert vorher, verwende einfache Variable in f-string.
    avail_height = id["screen_height"] - 25

    # Canvas-Fingerprint: Perlin-Noise basierter konsistenter Hash
    # Wir überschreiben getImageData() und toDataURL() um konsistente
    # Pixel-Werte zurückzugeben (nicht zufällig, konsistent pro Session).

    js = f"""
    (function() {{
        'use strict';

        // ═══════════════════════════════════════════════════════════════
        // 1. navigator.webdriver (MUSS zuerst!)
        // ═══════════════════════════════════════════════════════════════
        // WARUM? forensic-v6.2.0 prüft als ERSTES navigator.webdriver.
        // Wenn true → sofort Bot-Flag, keine weiteren Checks nötig.
        if (typeof navigator !== 'undefined') {{
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined,
                configurable: true,
                enumerable: true
            }});
        }}

        // ═══════════════════════════════════════════════════════════════
        // 2. User-Agent + Platform
        // ═══════════════════════════════════════════════════════════════
        // WARUM? HeadlessChrome im UA = sofort erkannt.
        // Echter Mac Chrome UA = konsistent mit WebGL (Apple M3).
        Object.defineProperty(navigator, 'userAgent', {{
            get: () => '{id["user_agent"]}',
            configurable: true,
            enumerable: true
        }});

        Object.defineProperty(navigator, 'platform', {{
            get: () => '{id["platform"]}',
            configurable: true,
            enumerable: true
        }});

        // ═══════════════════════════════════════════════════════════════
        // 3. Plugins (Headless = leer = verdächtig)
        // ═══════════════════════════════════════════════════════════════
        // WARUM? forensic-v6.2.0 zählt Plugins. 0 = Bot.
        // Echte Chrome-Installation hat 2-5 Plugins.
        var fakePlugins = {plugins_json};
        Object.defineProperty(navigator, 'plugins', {{
            get: () => {{
                var arr = fakePlugins.map(function(p, i) {{
                    var plugin = {{
                        name: p.name,
                        filename: p.filename,
                        description: p.description,
                        length: 1,
                        item: function(idx) {{ return this; }},
                        namedItem: function(name) {{ return this; }}
                    }};
                    return plugin;
                }});
                arr.length = fakePlugins.length;
                arr.item = function(idx) {{ return this[idx]; }};
                arr.namedItem = function(name) {{
                    return this.find(function(p) {{ return p.name === name; }});
                }};
                return arr;
            }},
            configurable: true,
            enumerable: true
        }});

        // ═══════════════════════════════════════════════════════════════
        // 4. Screen-Resolution (nicht Headless-Default 800x600)
        // ═══════════════════════════════════════════════════════════════
        // WARUM? Headless Chrome hat 800x600. MacBook Pro hat 1512x982.
        // forensic-v6.2.0 prüft screen.width + screen.height.
        if (typeof screen !== 'undefined') {{
            Object.defineProperty(screen, 'width', {{
                get: () => {id["screen_width"]},
                configurable: true
            }});
            Object.defineProperty(screen, 'height', {{
                get: () => {id["screen_height"]},
                configurable: true
            }});
            Object.defineProperty(screen, 'availWidth', {{
                get: () => {id["screen_width"]},
                configurable: true
            }});
            Object.defineProperty(screen, 'availHeight', {{
                get: () => {avail_height},  // Minus Dock/Menüleiste
                configurable: true
            }});
            Object.defineProperty(screen, 'colorDepth', {{
                get: () => {id["screen_color_depth"]},
                configurable: true
            }});
            Object.defineProperty(screen, 'pixelDepth', {{
                get: () => {id["screen_color_depth"]},
                configurable: true
            }});
        }}

        // devicePixelRatio (Retina = 2)
        if (typeof window !== 'undefined') {{
            Object.defineProperty(window, 'devicePixelRatio', {{
                get: () => {id["screen_pixel_ratio"]},
                configurable: true
            }});
        }}

        // ═══════════════════════════════════════════════════════════════
        // 5. Hardware-Concurrency + Device Memory
        // ═══════════════════════════════════════════════════════════════
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {id["hardware_concurrency"]},
            configurable: true
        }});

        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {id["device_memory"]},
            configurable: true
        }});

        // ═══════════════════════════════════════════════════════════════
        // 6. Languages + Timezone
        // ═══════════════════════════════════════════════════════════════
        Object.defineProperty(navigator, 'languages', {{
            get: () => {languages_json},
            configurable: true
        }});

        Object.defineProperty(navigator, 'language', {{
            get: () => '{id["languages"][0]}',
            configurable: true
        }});

        // ═══════════════════════════════════════════════════════════════
        // 7. WebGL-Spoofing (CORE — kritisch für forensic-v6.2.0!)
        // ═══════════════════════════════════════════════════════════════
        // WARUM? WebGL-Renderer "ANGLE (Apple, Apple M3 Pro, OpenGL 4.1)"
        // vs "ANGLE (Google, Vulkan 1.3)" (Headless).
        // forensic-v6.2.0 prüft vendor + renderer String.
        //
        // BUGFIX (2026-05-09): Vorher war `default: return target[name]` —
        // `target` ist hier eine FUNKTION (origGetParam), kein Array/Dict.
        // `func[name]` auf eine Funktion = undefined (oder Browser-spezifisch).
        // Fix: `target.call(ctx, name)` ruft die originale Funktion korrekt auf.
        var spoofWebGL = function() {{
            var getParameterProxy = function(origFn, ctx, param) {{
                switch(param) {{
                    case 0x1F00: return '{id["webgl_vendor"]}';  // VENDOR
                    case 0x1F01: return '{id["webgl_renderer"]}';  // RENDERER
                    case 0x9245: return '{id["webgl_unmasked_vendor"]}';  // UNMASKED_VENDOR_WEBGL
                    case 0x9246: return '{id["webgl_unmasked_renderer"]}';  // UNMASKED_RENDERER_WEBGL
                    default: return origFn.call(ctx, param);  // BUGFIX: call() statt [param]
                }}
            }};

            // Override WebGLRenderingContext
            var origGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, attrs) {{
                var ctx = origGetContext.call(this, type, attrs);
                if (ctx && (type === 'webgl' || type === 'experimental-webgl')) {{
                    var origGetParam = ctx.getParameter;
                    ctx.getParameter = function(param) {{
                        return getParameterProxy(origGetParam, ctx, param);
                    }};
                }}
                return ctx;
            }};
        }};
        spoofWebGL();

        // ═══════════════════════════════════════════════════════════════
        // 8. Canvas-Fingerprint-Randomization (konsistent!)
        // ═══════════════════════════════════════════════════════════════
        // WARUM? forensic-v6.2.0 malt ein kleines Bild und hashed es.
        // Wir addieren einen konsistenten Perlin-Noise-Offset zu jedem Pixel.
        // WICHTIG: KONSISTENT (selber Wert pro Session), nicht zufällig!
        var canvasSeed = {id["canvas_seed"]};

        // Simple seeded random (Mulberry32)
        var seededRandom = function(seed) {{
            return function() {{
                var t = seed += 0x6D2B79F5;
                t = Math.imul(t ^ (t >>> 15), t | 1);
                t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
                return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
            }};
        }};
        var rng = seededRandom(canvasSeed);

        // Override getImageData
        var origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
            var imgData = origGetImageData.call(this, x, y, w, h);
            var data = imgData.data;
            // Add subtle consistent noise (±2 to RGB channels)
            for (var i = 0; i < data.length; i += 4) {{
                var noise = Math.floor(rng() * 4) - 2;  // -2, -1, 0, 1
                data[i] = Math.max(0, Math.min(255, data[i] + noise));     // R
                data[i+1] = Math.max(0, Math.min(255, data[i+1] + noise)); // G
                data[i+2] = Math.max(0, Math.min(255, data[i+2] + noise)); // B
                // Alpha nicht ändern!
            }}
            return imgData;
        }};

        // Override toDataURL (muss konsistent mit getImageData sein)
        var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function() {{
            // Wenn context existiert, rufe getImageData auf um Noise zu applizieren
            var ctx = this.getContext('2d');
            if (ctx) {{
                ctx.getImageData(0, 0, 1, 1);  // Trigger noise (Seiteneffekt!)
            }}
            return origToDataURL.apply(this, arguments);
        }};

        // ═══════════════════════════════════════════════════════════════
        // 9. chrome.runtime (muss existieren bei echtem Chrome)
        // ═══════════════════════════════════════════════════════════════
        if (typeof window !== 'undefined' && !window.chrome) {{
            window.chrome = {{}};
        }}
        if (window.chrome && !window.chrome.runtime) {{
            window.chrome.runtime = {{}};
            Object.defineProperty(window.chrome.runtime, 'OnInstalledReason', {{
                get: () => ({{CHROME_UPDATE: 'chrome_update', UPDATE: 'update', INSTALL: 'install'}})
            }});
        }}

        // ═══════════════════════════════════════════════════════════════
        // 10. Permissions-API (Notifications = "prompt" statt "denied")
        // ═══════════════════════════════════════════════════════════════
        if (typeof navigator !== 'undefined' && navigator.permissions) {{
            var origQuery = navigator.permissions.query;
            navigator.permissions.query = function(args) {{
                if (args.name === 'notifications') {{
                    return Promise.resolve({{state: 'prompt'}});
                }}
                return origQuery.apply(this, arguments);
            }};
        }}

        // ═══════════════════════════════════════════════════════════════
        // 11. AudioContext-Spoofing (SampleRate)
        // ═══════════════════════════════════════════════════════════════
        if (typeof window !== 'undefined' && window.AudioContext) {{
            var OrigAudioContext = window.AudioContext || window.webkitAudioContext;
            if (OrigAudioContext) {{
                window.AudioContext = function() {{
                    var ctx = new OrigAudioContext();
                    // Spoof sampleRate
                    Object.defineProperty(ctx, 'sampleRate', {{
                        get: () => {id["audio_sample_rate"]},
                        configurable: true
                    }});
                    Object.defineProperty(ctx, 'destination', {{
                        get: () => ({{
                            channelCount: {id["audio_channel_count"]},
                            maxChannelCount: {id["audio_channel_count"]}
                        }}),
                        configurable: true
                    }});
                    return ctx;
                }};
            }}
        }}

        // ═══════════════════════════════════════════════════════════════
        // ERGEBNIS
        // ═══════════════════════════════════════════════════════════════
        return 'STEALTH_INJECTED: ' + navigator.userAgent.substring(0, 40);
    }})();
    """

    return js.strip()


def get_identity_hash(identity: dict[str, Any] | None = None) -> str:
    """Generiert Hash der Identität (für Session-Validierung)."""
    id = identity or FAKE_IDENTITY
    return hashlib.sha256(json.dumps(id, sort_keys=True).encode()).hexdigest()[:16]


# FastAPI Integration
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/stealth", tags=["stealth"])


class StealthInjectRequest(BaseModel):
    ws_url: str  # CDP WebSocket URL
    identity_seed: int | None = None  # Optional: custom seed for identity


class StealthInjectResponse(BaseModel):
    success: bool
    result: str
    identity_hash: str
    vectors_spoofed: int


@router.post("/inject", response_model=StealthInjectResponse)
async def inject_stealth(req: StealthInjectRequest):
    """
    Injected Stealth-JS auf eine Seite via CDP.

    Args:
        ws_url: CDP WebSocket URL der Ziel-Seite
        identity_seed: Optionaler Seed für konsistente Identität

    Returns:
        Erfolg + Anzahl der gespoofen Vektoren

    Beispiel:
        POST /stealth/inject
        {"ws_url": "ws://127.0.0.1:9224/devtools/page/..."}
    """
    import websockets

    # Generate identity (optional custom seed)
    identity = FAKE_IDENTITY.copy()
    if req.identity_seed:
        identity["canvas_seed"] = req.identity_seed

    js = generate_stealth_js(identity)

    try:
        async with websockets.connect(req.ws_url) as ws:
            await ws.send(
                json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js}})
            )
            resp = await ws.recv()
            data = json.loads(resp)
            result = data.get("result", {}).get("result", {}).get("value", "ERROR")

            return StealthInjectResponse(
                success=result.startswith("STEALTH_INJECTED"),
                result=result,
                identity_hash=get_identity_hash(identity),
                vectors_spoofed=11,  # Alle 11 Vektoren
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/identity")
async def get_current_identity():
    """
    Gibt die aktuelle Fake-Identität zurück.

    Returns:
        Aktuelle Identity-Werte (konsistente Fake-Hardware).
    """
    return {
        "identity": FAKE_IDENTITY,
        "hash": get_identity_hash(),
        "description": (
            'MacBook Pro 14", Apple M3 Pro, Chrome 147, macOS 15.4, '
            "1512x982 Retina Display, 18GB RAM, 12 Cores"
        ),
    }


@router.post("/validate")
async def validate_stealth(req: StealthInjectRequest):
    """
    Prüft ob Stealth-Injection erfolgreich war.

    Tests:
    1. navigator.webdriver = undefined
    2. navigator.userAgent = echter Chrome (nicht Headless)
    3. navigator.plugins.length > 0
    4. screen.width > 1000 (nicht 800x600)

    Returns:
        {all_passed, details: {vector: bool}}
    """
    import websockets

    test_js = """
    JSON.stringify({
        webdriver_undefined: typeof navigator.webdriver === 'undefined',
        userAgent_not_headless: !navigator.userAgent.includes('Headless'),
        plugins_exist: navigator.plugins.length > 0,
        screen_not_800x600: screen.width > 1000 && screen.height > 600,
        webgl_vendor_apple: (function() {
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl');
            if (!gl) return false;
            var vendor = gl.getParameter(0x9245);  // UNMASKED_VENDOR
            return vendor && vendor.includes('Apple');
        })(),
        canvas_fingerprint_different: (function() {
            var c1 = document.createElement('canvas');
            var ctx1 = c1.getContext('2d');
            ctx1.fillText('test', 10, 10);
            var d1 = ctx1.getImageData(0, 0, 50, 50).data[0];

            var c2 = document.createElement('canvas');
            var ctx2 = c2.getContext('2d');
            ctx2.fillText('test', 10, 10);
            var d2 = ctx2.getImageData(0, 0, 50, 50).data[0];

            // Noise sollte konsistent sein (selber Wert)
            return d1 === d2;
        })()
    })
    """

    try:
        async with websockets.connect(req.ws_url) as ws:
            await ws.send(
                json.dumps(
                    {"id": 1, "method": "Runtime.evaluate", "params": {"expression": test_js}}
                )
            )
            resp = await ws.recv()
            data = json.loads(resp)
            result_str = data.get("result", {}).get("result", {}).get("value", "{}")
            results = json.loads(result_str)

            all_passed = all(results.values())

            return {
                "all_passed": all_passed,
                "details": results,
                "identity_hash": get_identity_hash(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = [
    "generate_stealth_js",
    "get_identity_hash",
    "FAKE_IDENTITY",
    "router",
]
