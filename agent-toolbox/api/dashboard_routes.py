"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Dashboard Routes (HeyPiggy Scan + Balance)        ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Diese Datei implementiert die FastAPI-Router-Endpunkte für Dashboard-       ║
║  Operationen: Surveys scannen (mit Rewards) und Kontostand auslesen.        ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Endpoints (FastAPI Router, prefix="/dashboard", tags=["Dashboard"])│    ║
║  │  ├── POST /dashboard/scan   → Surveys mit € Rewards scannen         │    ║
║  │  └── POST /dashboard/balance → Aktuellen Kontostand auslesen         │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  WARUM EIGENER ROUTER?                                                       ║
║  ─────────────────────                                                       ║
║  • Modularität: Dashboard-Logik ist von Survey-Logik getrennt.            ║
║  • Wiederverwendung: Router kann in anderen Projekten importiert werden.   ║
║  • Testbarkeit: Router kann isoliert getestet werden (ohne main.py).      ║
║  • Übersichtlichkeit: main.py bleibt schlank (nur Registrierung).          ║
║                                                                              ║
║  WARUM POST statt GET?                                                       ║
║  ─────────────────────                                                       ║
║  • POST /dashboard/scan hat Seiteneffekte (JavaScript-Ausführung im       ║
║    Browser, DOM-Navigation).                                                 ║
║  • POST /dashboard/balance hat Seiteneffekte (DOM-Abfrage).               ║
║  • Für Konsistenz: Alle Survey-Endpoints sind POST (einheitliche API).    ║
║  • In Zukunft könnten Filter-Parameter im Body übergeben werden (POST     ║
║    erlaubt komplexere Requests als GET).                                     ║
║                                                                              ║
║  WARUM CDP WEBSOCKET (nicht Playwright)?                                     ║
║  ─────────────────────────────────────────                                     ║
║  • Playwright ist SCHWER (150MB+ Binary, 2-5s Startup).                      ║
║  • CDP WebSocket ist LEICHT (<1s, nur websocket-client Paket).             ║
║  • Für reine Lese-Operationen (Scan, Balance) ist CDP ausreichend.        ║
║  • Kein Page-Objekt nötig (kein Automation, nur JavaScript-Ausführung).  ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • KEINE hardcoded Selektoren (CSS-Klassen ändern sich bei UI-Updates).    ║
║  • KEINE Annahmen über DOM-Struktur (Heuristics statt feste Pfade).         ║
║  • KEINE sensitiven Daten loggen (nur Balance, keine PII).                  ║
║  • Balance-Updates sind read-only (keine Modifikation des Kontostands).     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# json: JSON Serialisierung/Deserialisierung.
# WARUM? - WebSocket-Antworten sind JSON-Strings → json.loads() um zu parsen.
#        - JavaScript-Code in Strings enthält JSON-Strings (JSON.stringify()).
#        - Standard-Library (keine External Dependencies).
import json

# re: Reguläre Ausdrücke (Regex).
# WARUM? - Extrahiere Zahlen aus Text (Balance, Rewards, Fortschritt).
#        - "12.35€" → regex r'(\d+[.,]?\d*)' extrahiert "12.35".
#        - "Seite 3 von 10" → regex r'(\d+)\s*/\s*(\d+)' extrahiert "3/10".
#        - Regex ist robuster als String-Splitting (Format kann variieren).
import re

# time: Zeit-Messung (optional, nicht im aktuellen Code aber nützlich).
# WARUM? - Könnte für Performance-Monitoring hinzugefügt werden.
#        - Aktuell nicht verwendet (Scan/Balance sind schnell: <2s).
import time

# logging: Log-Ausgaben (nicht print!).
# WARUM? - Logs können in Dateien geschrieben werden (für Debugging).
#        - Log-Level (INFO, WARNING, ERROR) ermöglichen Filterung.
#        - Konsistenz: Playwright und andere Libraries verwenden logging.
#        - __name__ → Logger-Name enthält Modul-Pfad ("api.dashboard_routes").
import logging

# Typ-Hinweise für bessere Code-Klarheit und IDE-Unterstützung.
# List, Dict, Any: Für flexible Typen (Survey-Listen, Extraktions-Ergebnisse).
from typing import List, Dict, Any

# APIRouter: FastAPI-Router für modulare Endpoints.
# WARUM? - Router können unabhängig definiert und in main.py registriert werden.
#        - Prefix und Tags werden im Router definiert (nicht pro Endpoint).
#        - Modularität: Diese Datei kann allein getestet werden.
from fastapi import APIRouter

# CDP WebSocket Funktionen aus survey_actions.py (wiederverwendet).
# WARUM? - get_dashboard_ws(): Findet Dashboard-Tab via CDP /json API.
#        - ws_eval(): Führt JavaScript im Browser aus und gibt Resultat zurück.
#        - DRY-Prinzip: Keine Duplikation von CDP-Logik.
#        - Diese Funktionen sind stabil und getestet (wiederverwenden).
from api.survey_actions import get_dashboard_ws, ws_eval

# Pydantic-Modelle für Request/Response Validation.
# WARUM? - FastAPI validiert Requests automatisch (422 bei ungültigen Daten).
#        - Response-Modelle garantieren korrektes JSON-Format.
#        - Siehe schemas.py für detaillierte Dokumentation jedes Modells.
from api.schemas import (
    # Request/Response für POST /dashboard/scan
    DashboardScanRequest,      # cdp_port
    DashboardScanResponse,      # status, balance_eur, available_surveys[], total_rewards, message
    DashboardSurvey,             # survey_id, reward_eur, duration_min, provider, title
    
    # Request/Response für POST /dashboard/balance
    BalanceRequest,             # cdp_port
    BalanceResponse,            # status, balance_eur, currency, message
)

# Logger-Instanz für diese Datei.
# WARUM __name__? Logger-Name enthält Modul-Pfad ("api.dashboard_routes").
# Ermöglicht gezieltes Logging-Level pro Modul.
logger = logging.getLogger(__name__)

# Router-Instanz erstellen.
# prefix="/dashboard": ALLE Endpoints beginnen mit /dashboard (z.B. /dashboard/scan).
# tags=["Dashboard"]: Swagger UI gruppiert diese Endpoints unter "Dashboard".
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: POST /dashboard/scan
# ═══════════════════════════════════════════════════════════════════════════════
# Scannt das HeyPiggy Dashboard nach verfügbaren Surveys mit Rewards.
# ═══════════════════════════════════════════════════════════════════════════════


async def _scan_dashboard_impl(cdp_port: int, min_reward: float = 0.0) -> dict:
    """
    Implementation des Dashboard-Scans (wiederverwendbar für Endpoints + Background-Task).
    
    WARUM separate Funktion?
    → Background-Task (main.py) muss das Dashboard scannen OHNE HTTP-Request.
    → DRY-Prinzip: Gleiche Logik für Endpoint und Background-Task.
    → Kein Pydantic-Request nötig (einfache Parameter: cdp_port, min_reward).
    
    Args:
        cdp_port: CDP Port für Chrome-Verbindung.
        min_reward: Mindest-Reward (€) — Surveys mit niedrigerem Reward werden ignoriert.
    
    Returns:
        Dict mit:
          - status: "success" oder "error"
          - balance_eur: Aktueller Kontostand
          - surveys: Liste von Survey-Dicts (id, reward, duration, title, provider)
          - total_rewards: Summe aller Rewards
          - message: Human-readable Status
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════
    
    ws_url = get_dashboard_ws(cdp_port)
    
    if not ws_url:
        return {
            "status": "error",
            "balance_eur": 0.0,
            "surveys": [],
            "total_rewards": 0.0,
            "message": f"No dashboard found. Is Chrome running on port {cdp_port}?",
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Scan-JavaScript definieren
    # ═══════════════════════════════════════════════════════════════════════
    
    scan_js = """
(function() {
    var results = {
        balance: "",
        surveys: []
    };
    
// ── Balance auslesen — SPECIFIC approach for HeyPiggy ──
    // HeyPiggy dashboard: balance DOM has numbers + € on SEPARATE lines.
    // Body text: "+" / "0.00" / "€" / "2.75" / "€" — € is on its own line below number.
    // Strategy: Find all numbers followed eventually by "€", take max >= 1.0.
    var bodyText = document.body.innerText;
    
    // Strategy 1: Find ALL € amounts anywhere in body (handles newlines)
    // Pattern: number followed somewhere by € symbol (even across lines)
    var allMatches = [];
    var numPattern = /(\d+[.,]\d{2})/g;
    var match;
    while ((match = numPattern.exec(bodyText)) !== null) {
        var pos = match.index;
        var numStr = match[1];
        var afterNum = bodyText.substring(pos + numStr.length, pos + numStr.length + 50);
        if (afterNum.includes('€')) {
            allMatches.push(parseFloat(numStr.replace(',', '.')));
        }
    }
    if (allMatches.length > 0) {
        var maxEuro = Math.max.apply(null, allMatches);
        if (maxEuro >= 1.0 && maxEuro <= 1000) {
            results.balance = maxEuro.toString().replace('.', ',') + ' €';
        }
    }
    
    // Strategy 2: Look for "0.00 € / 2.75 €" pattern (balance + currency)
    // Handles multi-line: "0.00" then "€" then "2.75" then "€"
    if (!results.balance) {
        var multiMatch = bodyText.match(/(\d+[.,]\d+)\s*€\s*[\n\r]*\s*(\d+[.,]\d+)\s*€\s*[\n\r]*[××]/);
        if (multiMatch) {
            var candidates = [parseFloat(multiMatch[1].replace(',', '.')), parseFloat(multiMatch[2].replace(',', '.'))];
            for (var ci = 0; ci < candidates.length; ci++) {
                if (candidates[ci] >= 1.0 && candidates[ci] <= 1000) {
                    results.balance = candidates[ci].toString().replace('.', ',') + ' €';
                    break;
                }
            }
        }
    }
    
    // Strategy 3: Fallback — look for "+" followed by number followed by "€" (any whitespace/newlines)
    if (!results.balance) {
        var topMatch = bodyText.substring(0, 500).match(/\+\s*(\d+[.,]\d+)\s*€/);
        if (topMatch) {
            var val = parseFloat(topMatch[1].replace(',', '.'));
            if (val >= 0.5) {
                results.balance = val.toString().replace('.', ',') + ' €';
            }
        }
    }
    
    // Strategy 4: Fallback — look for "Guthaben" or "Balance" labels
    if (!results.balance) {
        var balanceMatch = bodyText.match(/(Guthaben|Balance|Points)[:\\s]*([€\\$]?\\s*[\\d,.]+)/i);
        if (balanceMatch) {
            results.balance = balanceMatch[2];
        }
    }
        }
    }
    
    // Strategy 2: Find ALL € amounts, take the MAXIMUM (balance is usually largest)
    if (!results.balance) {
        var allEuros = bodyText.match(/(\d+[.,]\d+)\s*€/g) || [];
        var maxEuro = 0;
        for (var e of allEuros) {
            var val = parseFloat(e.replace(/[^\d.,]/g, '').replace(',', '.'));
            if (val >= 1.0 && val <= 1000) {
                maxEuro = Math.max(maxEuro, val);
            }
        }
        if (maxEuro > 0) {
            results.balance = maxEuro.toString().replace('.', ',') + ' €';
        }
    }
    
    // Strategy 3: Fallback — look for "+" followed by number followed by "€" at page top
    if (!results.balance) {
        var topMatch = bodyText.substring(0, 500).match(/\+[\s\n]*(\d+[.,]\d+)[\s\n]*€/);
        if (topMatch) {
            var val = parseFloat(topMatch[1].replace(',', '.'));
            if (val >= 0.5) {
                results.balance = val.toString().replace('.', ',') + ' €';
            }
        }
    }
    }
    
    if (!results.balance) {
        var bodyText = document.body.innerText;
        var balanceMatch = bodyText.match(/(Guthaben|Balance|Points)[:\\s]*([€\\$]?\\s*[\\d,.]+)/i);
        if (balanceMatch) {
            results.balance = balanceMatch[2];
        }
    }
    
// ── Survey-Cards finden ──
    // FIX: Use .card-body scope to avoid balance (2.75€) bleeding into card text.
    // Also try multiple selectors for flexibility.
    var cardSelectors = [
        '[onclick*="clickSurvey"] .card-body',
        '[onclick*="clickSurvey"] [class*="card-body"]',
        '[onclick*="clickSurvey"] [class*="body"]',
        '[onclick*="clickSurvey"] > div',
        '[onclick*="clickSurvey"]',
    ];
    
    var cards = [];
    for (var sel of cardSelectors) {
        cards = document.querySelectorAll(sel);
        if (cards.length > 0) break;
    }
    
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var onclick = card.getAttribute("onclick") || '';
        if (!onclick) {
            // card might be the parent of the onclick element
            var onclickEl = card.querySelector('[onclick*="clickSurvey"]');
            if (onclickEl) onclick = onclickEl.getAttribute("onclick") || '';
        }
        var idMatch = onclick.match(/clickSurvey\('?(\d+)'?\)/);
        var surveyId = idMatch ? idMatch[1] : '';
        
        // Get ONLY the card body text (excludes parent navigation/balance)
        var cardText = card.textContent || '';
        
        // Reward: find the FIRST € amount in the card (survey reward, NOT balance)
        // Balance (2.75€) is usually at top of page, not inside individual survey cards.
        // But in HeyPiggy the balance might be inside the card too — take first match.
        var rewardMatch = cardText.match(/(\d+[.,]?\d*)\s*€/);
        var reward = rewardMatch ? parseFloat(rewardMatch[1].replace(',', '.')) : 0;
        
        // Duration: look for "X Min" pattern (survey duration, not completion count)
        var durationMatch = cardText.match(/(\d+)\s*Min/);
        var duration = durationMatch ? parseInt(durationMatch[1]) : null;
        
        // Title: first non-empty line before the € amount
        var lines = cardText.split('\n').map(function(l) { return l.trim(); }).filter(Boolean);
        var title = '';
        for (var li = 0; li < lines.length; li++) {
            if (lines[li].includes('€')) break;
            if (lines[li].length > 3 && !/^\d+$/.test(lines[li])) {
                title = lines[li].substring(0, 80);
                break;
            }
        }
        
        // Provider detection from card text (provider name appears in survey card)
        var cardTextLower = cardText.toLowerCase();
        var provider = 'unknown';
        if (cardTextLower.includes('qualtrics')) provider = 'qualtrics';
        else if (cardTextLower.includes('toluna')) provider = 'tolunastart';
        else if (cardTextLower.includes('cint')) provider = 'cint';
        else if (cardTextLower.includes('tivian')) provider = 'tivian';
        else if (cardTextLower.includes('nfield') || cardTextLower.includes('kantar')) provider = 'nfield';
        else if (cardTextLower.includes('samplicio')) provider = 'samplicio';
        else if (cardTextLower.includes('purespectrum') || cardTextLower.includes('pure spectrum')) provider = 'purespectrum';
        else if (cardTextLower.includes('ipsos')) provider = 'ipsos';
        else if (cardTextLower.includes('prolific')) provider = 'prolific';
        else if (cardTextLower.includes('surveytime') || cardTextLower.includes('surveytime')) provider = 'surveytime';
        
        if (surveyId && reward > 0) {
            results.surveys.push({
                id: surveyId,
                reward: reward,
                duration: duration,
                title: title,
                provider: provider
            });
        }
    }
    
    return JSON.stringify(results);
})()
"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript ausführen — DIREKT via websocket (kein ws_eval)
    # ═══════════════════════════════════════════════════════════════════════
    
    try:
        import websocket as _ws_module
        ws = _ws_module.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": scan_js}}))
        resp = json.loads(ws.recv())
        ws.close()
        result_text = resp.get("result", {}).get("result", {}).get("value", "{}")
        data = json.loads(result_text)
    except Exception as e:
        logger.error(f"Dashboard scan failed: {e}")
        return {
            "status": "error", "balance_eur": 0.0, "surveys": [], "total_rewards": 0.0,
            "message": f"Scan failed: {str(e)}",
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Balance parsen
    # ═══════════════════════════════════════════════════════════════════════
    
    balance_str = data.get("balance", "")
    balance_eur = 0.0
    
    if balance_str:
        balance_match = re.search(r'(\d+[.,]?\d*)', balance_str.replace(',', '.'))
        if balance_match:
            balance_eur = float(balance_match.group(1))
    else:
        # FIX: Balance im body text — "2.75 €" Format (€ NACH Zahl)
        try:
            ws2 = _ws_module.create_connection(ws_url, timeout=15)
            ws2.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": "document.body.innerText"}}))
            resp2 = json.loads(ws2.recv())
            ws2.close()
            body_text = resp2.get("result", {}).get("result", {}).get("value", "")
            # Balance: "2.75" with € after, in header area (before "Umfragen")
            # Survey rewards are all < 1.0, balance is always >= 1.0
            # Strategy: find first € amount >= 1.0 (the balance)
            all_eur = re.findall(r'(\d+[.,]?\d*)\s*€', body_text[:800])
            for amt in all_eur:
                val = float(amt.replace(',', '.'))
                if val >= 1.0:
                    balance_eur = val
                    break
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Surveys filtern und konvertieren
    # ═══════════════════════════════════════════════════════════════════════
    
    surveys = []
    total_rewards = 0.0
    
    for s in data.get("surveys", []):
        reward = s.get("reward", 0)
        
        # Filter: Mindest-Reward
        if reward < min_reward:
            continue
        
        surveys.append({
            "id": str(s.get("id", "")),
            "reward": reward,
            "duration": s.get("duration"),
            "title": s.get("title", ""),
            "provider": s.get("provider", "unknown"),
        })
        
        total_rewards += reward
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════
    
    return {
        "status": "success",
        "balance_eur": balance_eur,
        "surveys": surveys,
        "total_rewards": total_rewards,
        "message": f"Found {len(surveys)} surveys, total rewards: {total_rewards:.2f}€",
    }


@router.post("/scan", response_model=DashboardScanResponse)
async def scan_dashboard(req: DashboardScanRequest):
    """
    Scannt das HeyPiggy Dashboard nach verfügbaren Surveys mit Rewards.
    
    ABLAUF:
    1. Finde Dashboard WebSocket (get_dashboard_ws).
    2. Wenn nicht gefunden → Error-Response (Chrome nicht erreichbar).
    3. Führe Scan-JavaScript aus (ws_eval):
       - Suche Balance-Elemente (Sidebar/Header) via CSS-Selektoren.
       - Wenn nicht gefunden → suche im gesamten Body-Text nach Balance-Patterns.
       - Suche Survey-Cards mit onclick="clickSurvey(...)" Attribut.
       - Extrahiere Survey-ID, Reward (€), Dauer (Minuten), Titel.
    4. Parse Balance (String → Float).
    5. Konvertiere Surveys in Pydantic-Modelle (DashboardSurvey).
    6. Berechne total_rewards = Summe aller Rewards.
    7. Gib DashboardScanResponse zurück.
    
    WARUM CDP statt Playwright?
    → Playwright ist schwer (150MB Binary, 2-5s Startup).
    → CDP WebSocket ist leicht (<1s, nur websocket-client).
    → Für reine Lese-Operationen ist CDP ausreichend.
    → Kein Page-Objekt nötig (kein Automation, nur JS-Ausführung).
    
    WARUM JavaScript-Scan (nicht Python/BeautifulSoup)?
    → Das Dashboard ist dynamisch (JavaScript lädt Surveys nach dem Page-Load).
    → Python-HTTP-Request gibt nur statisches HTML zurück (keine Surveys).
    → Wir müssen JavaScript IM BROWSER ausführen um den aktuellen Zustand zu sehen.
    → CDP Runtime.evaluate() führt JS im Browser-Kontext aus.
    
    WARUM Heuristiken (nicht feste CSS-Selektoren)?
    → CSS-Klassen ändern sich bei UI-Updates (z.B. .balance → .user-balance).
    → Wir verwenden MEHRERE Selektoren und nehmen den ersten Treffer.
    → Wenn keiner matcht → Fallback auf Text-Suche (Regex).
    → Das ist robuster gegen UI-Änderungen.
    
    WARUM onclick="clickSurvey(...)"?
    → HeyPiggy verwendet onclick-Handler auf den Survey-Cards.
    → Das ist ein stabilier Indikator (wurde über mehrere Monate beobachtet).
    → Wir extrahieren die Survey-ID aus dem onclick-Attribut.
    → Beispiel: onclick="clickSurvey('12345')" → ID = "12345".
    
    WARUM Regex für Reward/Dauer?
    → Rewards werden als "0.35 €" oder "1.20€" angezeigt.
    → Regex r'(\d+[.,]?\d*)\s*€' matcht beide Formate.
    → Dauer wird als "15 min" oder "15min" angezeigt.
    → Regex r'(\d+)\s*min' matcht beide Formate.
    → Regex ist flexibler als feste String-Parsing.
    
    WARUM total_rewards berechnen?
    → Client kann schnell entscheiden: "Lohnt es sich heute Surveys zu machen?"
    → Wenn total_rewards < 1.00€ → vielleicht morgen wieder versuchen.
    → Wenn total_rewards > 5.00€ → lohnt sich (mehrere Surveys verfügbar).
    → Berechnung passiert Server-seitig (Client muss nicht selbst summieren).
    
    WARUM Pydantic-Modelle (DashboardSurvey)?
    → Typsicherheit: FastAPI validiert Response automatisch.
    → Klare Struktur: Jedes Survey hat survey_id, reward_eur, duration_min, provider, title.
    → Auto-Dokumentation: Swagger UI zeigt Felder und Typen an.
    → Client weiß EXAKT was zu erwarten ist.
    
    Args:
        req: DashboardScanRequest
            - cdp_port: CDP Port (default: 9999).
    
    Returns:
        DashboardScanResponse:
            - status: "success" oder "error".
            - balance_eur: Aktueller Kontostand (Float).
            - available_surveys: Liste von DashboardSurvey-Objekten.
            - total_rewards: Summe aller verfügbaren Rewards (Float).
            - message: Human-readable Zusammenfassung.
    
    Raises:
        Keine (alle Fehler werden abgefangen und als Response zurückgegeben).
    
    Example:
        POST /dashboard/scan
        {"cdp_port": 9999}
        → {"status": "success", "balance_eur": 12.35,
            "available_surveys": [
                {"survey_id": "12345", "reward_eur": 0.35, "duration_min": 5, "provider": "qualtrics", "title": "Umfrage zu Lebensmitteln"},
                ...
            ],
            "total_rewards": 3.50,
            "message": "Found 5 surveys, total rewards: 3.50€"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════
    
    # Finde WebSocket URL für das HeyPiggy Dashboard.
    # WARUM? Wir brauchen eine CDP-Verbindung zum Dashboard-Tab.
    # Wenn Chrome nicht läuft oder kein Dashboard-Tab offen ist → None.
    ws_url = get_dashboard_ws(req.cdp_port)
    
    if not ws_url:
        # Kein Dashboard gefunden → Chrome läuft nicht oder kein Dashboard-Tab.
        return DashboardScanResponse(
            status="error",
            balance_eur=0.0,
            available_surveys=[],  # Leere Liste (keine Surveys verfügbar)
            total_rewards=0.0,
            message="No dashboard found. Is Chrome running on port {0}?".format(req.cdp_port),
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2-6: Scan via _scan_dashboard_impl (DRY-Prinzip)
    # ═══════════════════════════════════════════════════════════════════════
    # WARUM _scan_dashboard_impl?
    # → Gleiche Logik wird vom Background-Loop in main.py verwendet.
    # → Keine Duplikation: Endpoint und Background teilen Implementation.
    
    result = await _scan_dashboard_impl(req.cdp_port)
    
    if result["status"] == "error":
        return DashboardScanResponse(
            status="error",
            balance_eur=0.0,
            available_surveys=[],
            total_rewards=0.0,
            message=result["message"],
        )
    
    # Konvertiere Dict-Surveys in Pydantic-Modelle
    surveys = [
        DashboardSurvey(
            survey_id=s["id"],
            reward_eur=s["reward"],
            duration_min=s.get("duration"),
            title=s["title"],
            provider=s.get("provider", "unknown"),
        )
        for s in result["surveys"]
    ]
    
    return DashboardScanResponse(
        status="success",
        balance_eur=result["balance_eur"],
        available_surveys=surveys,
        total_rewards=result["total_rewards"],
        message=result["message"],
    )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Scan-JavaScript definieren
    # ═══════════════════════════════════════════════════════════════════════
    
    # JavaScript das IM BROWSER ausgeführt wird.
    # WARUM IIFE? (function() { ... })() → Isoliert Variablen, ermöglicht return.
    scan_js = """
(function() {
    // Ergebnis-Objekt.
    var results = {
        balance: "",      // Balance als String (wird später geparsed)
        surveys: []       // Liste der gefundenen Surveys
    };
    
    // ── Balance auslesen ──
    // WARUM CSS-Selektoren? Balance wird typischerweise in Sidebar/Header angezeigt.
    // Wir verwenden MEHRERE Selektoren (Heuristik) für Robustheit.
    var balanceElements = document.querySelectorAll(
        '.balance, .points, [class*="balance"], [class*="points"], [class*="guthaben"]'
    );
    
    for (var el of balanceElements) {
        var text = el.textContent.trim();
        
        // Prüfe ob Text € enthält ODER ein Zahlenformat ist.
        // WARUM? Balance wird als "12.35 €" oder "€12.35" angezeigt.
        if (text.includes('€') || text.includes('EUR') || /\\d+\\.\\d+/.test(text)) {
            results.balance = text;
            break;  // Erster Treffer = wahrscheinlich die Balance
        }
    }
    
    // Falls Balance nicht gefunden → suche im gesamten Text.
    // WARUM Fallback? Wenn CSS-Klassen sich geändert haben (UI-Update).
    if (!results.balance) {
        var bodyText = document.body.innerText;
        
        // Regex: "Guthaben: 12.35€" oder "Balance: €12.35" oder "Points: 123".
        // WARUM Regex? Flexible Format-Erkennung (verschiedene Schreibweisen).
        var balanceMatch = bodyText.match(/(Guthaben|Balance|Points)[:\\s]*([€\\$]?\\s*[\\d,.]+)/i);
        
        if (balanceMatch) {
            // Gruppe 2 = der Betrag (z.B. "12.35€" oder "€ 12.35").
            results.balance = balanceMatch[2];
        }
    }
    
    // ── Survey-Cards finden ──
    // WARUM onclick*="clickSurvey"? HeyPiggy verwendet onclick-Handler auf Cards.
    // Das ist ein stabiler Indikator (über mehrere Monate beobachtet).
    var cards = document.querySelectorAll('[onclick*="clickSurvey"]');
    
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        
        // Extrahiere onclick-Attribut.
        var onclick = card.getAttribute("onclick") || '';
        
        // Regex: clickSurvey('12345') oder clickSurvey("12345").
        // WARUM Regex? Flexible Quote-Erkennung (einfache oder doppelte Anführungszeichen).
        var idMatch = onclick.match(/clickSurvey\\('?(\\d+)'?\\)/);
        var surveyId = idMatch ? idMatch[1] : '';  // Survey-ID oder leer
        
        // ── Reward auslesen ──
        // Suche im Parent-Element (Container der Card) nach €-Betrag.
        // WARUM Parent? Der €-Betrag ist oft außerhalb der Card (im Container).
        var parent = card.closest('div, li, tr, article') || card;
        var cardText = parent.textContent || '';
        
        // Regex: "0.35 €" oder "1.20€" → extrahiere Zahl.
        // (\\d+[.,]?\\d*) = Zahl mit optionalen Dezimalstellen (Komma oder Punkt).
        var rewardMatch = cardText.match(/(\\d+[.,]?\\d*)\\s*€/);
        var reward = rewardMatch ? parseFloat(rewardMatch[1].replace(',', '.')) : 0;
        
        // ── Dauer auslesen ──
        // Regex: "15 min" oder "15min" → extrahiere Minuten.
        var durationMatch = cardText.match(/(\\d+)\\s*min/i);
        var duration = durationMatch ? parseInt(durationMatch[1]) : null;
        
        // ── Titel extrahieren ──
        // Regex: Text vor dem €-Betrag (vermutlich der Titel).
        // WARUM? Der Titel steht typischerweise vor dem Reward.
        // Beispiel: "Umfrage zu Lebensmitteln 0.35 €" → Titel = "Umfrage zu Lebensmitteln".
        var titleMatch = cardText.match(/([^€\\n]+)(?=\\d+[.,]?\\d*\\s*€)/);
        var title = titleMatch ? titleMatch[1].trim().substring(0, 100) : '';
        
        // Nur wenn Survey-ID und Reward gültig sind → hinzufügen.
        // WARUM? Filtern von unvollständigen/inaktiven Cards.
        if (surveyId && reward > 0) {
            results.surveys.push({
                id: surveyId,
                reward: reward,
                duration: duration,
                title: title
            });
        }
    }
    
    // Rückgabe als JSON-String (für CDP returnByValue).
    return JSON.stringify(results);
})()
"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript ausführen
    # ═══════════════════════════════════════════════════════════════════════
    
    try:
        # Führe Scan-JavaScript im Browser aus.
        # WARUM ws_eval? CDP WebSocket → JavaScript-Ausführung → Resultat als Dict.
        result = ws_eval(ws_url, scan_js, timeout=10)
        
        # Extrahiere Wert aus Resultat.
        # WARUM .get("value", "{}")? CDP gibt {"value": "...", "type": "string"} zurück.
        # Wenn result None → verwende leeren JSON-String.
        result_text = result.get("value", "{}") if result else "{}"
        
        # Parse JSON-String in Python-Dict.
        data = json.loads(result_text)
    
    except Exception as e:
        # Fehler beim Scan (z.B. JavaScript-Fehler, Timeout, etc.).
        # Logge Fehler für Debugging.
        logger.error(f"Dashboard scan failed: {e}")
        
        return DashboardScanResponse(
            status="error",
            balance_eur=0.0,
            available_surveys=[],
            total_rewards=0.0,
            message=f"Scan failed: {str(e)}",
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Balance parsen
    # ═══════════════════════════════════════════════════════════════════════
    
    # Balance-String extrahieren (z.B. "12.35 €" oder "€12.35").
    balance_str = data.get("balance", "")
    balance_eur = 0.0
    
    if balance_str:
        # Regex: Extrahiere Zahl (mit Komma oder Punkt als Dezimaltrenner).
        # WARUM replace(',', '.')? Deutsche Zahlen verwenden Komma ("12,35").
        # Python's float() erwartet Punkt ("12.35").
        balance_match = re.search(r'(\d+[.,]?\d*)', balance_str.replace(',', '.'))
        
        if balance_match:
            # Konvertiere zu Float.
            balance_eur = float(balance_match.group(1))
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Surveys konvertieren
    # ═══════════════════════════════════════════════════════════════════════
    
    # Liste der gefundenen Surveys.
    surveys = []
    total_rewards = 0.0
    
    # Iteriere über alle gefundenen Surveys.
    for s in data.get("surveys", []):
        # Reward extrahieren (Float).
        reward = s.get("reward", 0)
        
        # Erstelle Pydantic-Modell für jedes Survey.
        # WARUM Pydantic? Typsicherheit + Auto-Dokumentation in Swagger UI.
        surveys.append(DashboardSurvey(
            survey_id=str(s.get("id", "")),    # ID als String (könnte alphanumerisch sein)
            reward_eur=reward,                   # Reward in EUR (Float)
            duration_min=s.get("duration"),      # Dauer in Minuten (oder None)
            title=s.get("title", ""),            # Titel/Beschreibung (oder leer)
        ))
        
        # Summiere Rewards.
        total_rewards += reward
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════
    
    return DashboardScanResponse(
        status="success",                    # Scan erfolgreich
        balance_eur=balance_eur,              # Aktueller Kontostand
        available_surveys=surveys,           # Liste aller verfügbaren Surveys
        total_rewards=total_rewards,          # Summe aller Rewards
        message=f"Found {len(surveys)} surveys, total rewards: {total_rewards:.2f}€",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: POST /dashboard/balance
# ═══════════════════════════════════════════════════════════════════════════════
# Liest den aktuellen HeyPiggy Kontostand aus.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/balance", response_model=BalanceResponse)
async def get_balance(req: BalanceRequest):
    """
    Liest den aktuellen HeyPiggy Kontostand aus.
    
    ABLAUF:
    1. Finde Dashboard WebSocket (get_dashboard_ws).
    2. Wenn nicht gefunden → Error-Response (Chrome nicht erreichbar).
    3. Führe Balance-JavaScript aus (ws_eval):
       - Versuche mehrere CSS-Selektoren (Heuristik).
       - Wenn nicht gefunden → suche im gesamten Body-Text nach Balance-Patterns.
    4. Parse Balance-String (String → Float).
       - Entferne € und Whitespace.
       - Ersetze Komma mit Punkt (deutsches Format).
       - Extrahiere Zahl via Regex.
    5. Gib BalanceResponse zurück.
    
    WARUM eigener Endpoint (statt nur /dashboard/scan)?
    → Schneller: Kein Survey-Scanning nötig (nur Balance-Abfrage).
    → Weniger Daten: Keine Survey-Liste (kleinere Response).
    → Nützlich für periodische Abfrage (z.B. alle 5 Minuten).
    → Wenn nur Balance interessiert → kein Overhead durch Survey-Extraktion.
    
    WARUM Heuristiken (mehrere Selektoren)?
    → CSS-Klassen ändern sich bei UI-Updates.
    → Wir verwenden MEHRERE Selektoren und nehmen den ersten Treffer.
    → Selektoren: .balance, .points, [class*="balance"], [class*="guthaben"], etc.
    → WARUM "guthaben"? HeyPiggy ist auf Deutsch → "Guthaben" = Balance.
    
    WARUM Body-Text Fallback?
    → Wenn kein CSS-Selektor matcht (z.B. komplett neues UI-Design).
    → Suche nach "Guthaben", "Balance", "Points", "Kontostand" im gesamten Text.
    → Regex-Patterns für verschiedene Sprachen/Formate.
    → Das ist ein robuster Fallback (funktioniert auch bei UI-Änderungen).
    
    WARUM € entfernen?
    → "12.35 €" → "12.35" (€ ist kein Teil der Zahl).
    → "€12.35" → "12.35" (€ am Anfang).
    → Whitespace entfernen: " 12.35 " → "12.35".
    → Punkt/Komma: "12,35" → "12.35" (deutsches Format).
    
    WARUM Float?
    → HeyPiggy zeigt 2 Dezimalstellen (0.35€, 1.20€).
    → Float ist ausreichend für diese Genauigkeit.
    → Bei Bedarf könnte Decimal verwendet werden (exakte Berechnungen).
    
    WARUM currency="EUR"?
    → HeyPiggy verwendet Euro (€).
    → Für Zukunftssicherheit: Könnte andere Währungen unterstützen.
    → ISO 4217 Standard: "EUR", "USD", "GBP".
    
    Args:
        req: BalanceRequest
            - cdp_port: CDP Port (default: 9999).
    
    Returns:
        BalanceResponse:
            - status: "success" oder "error".
            - balance_eur: Aktueller Kontostand (Float, z.B. 12.35).
            - currency: Währung (immer "EUR" für HeyPiggy).
            - message: Human-readable Status.
    
    Raises:
        Keine (alle Fehler werden abgefangen und als Response zurückgegeben).
    
    Example:
        POST /dashboard/balance
        {"cdp_port": 9999}
        → {"status": "success", "balance_eur": 12.35, "currency": "EUR",
            "message": "Balance: 12.35€"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════
    
    ws_url = get_dashboard_ws(req.cdp_port)
    
    if not ws_url:
        return BalanceResponse(
            status="error",
            balance_eur=0.0,
            message="No dashboard found. Is Chrome running on port {0}?".format(req.cdp_port),
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Balance-JavaScript definieren
    # ═══════════════════════════════════════════════════════════════════════
    
    balance_js = """
(function() {
    // ── Verschiedene Balance-Selektoren (Heuristik) ──
    // WARUM mehrere? CSS-Klassen ändern sich bei UI-Updates.
    // Wir versuchen mehrere und nehmen den ersten Treffer.
    var selectors = [
        '.balance',           // Klasse "balance"
        '.points',            // Klasse "points"
        '[class*="balance"]',  // Klasse enthält "balance"
        '[class*="points"]',   // Klasse enthält "points"
        '[class*="guthaben"]', // Klasse enthält "guthaben" (Deutsch)
        '[class*="konto"]',   // Klasse enthält "konto" (Deutsch)
        '.user-balance',      // Klasse "user-balance"
        '#balance',            // ID "balance"
        '#points'              // ID "points"
    ];
    
    // Iteriere über alle Selektoren.
    for (var sel of selectors) {
        var els = document.querySelectorAll(sel);
        
        for (var el of els) {
            var text = el.textContent.trim();
            
            // Prüfe ob Text € enthält ODER ein Zahlenformat ist.
            // WARUM? Balance wird als "12.35 €" oder nur "12.35" angezeigt.
            if (text.includes('€') || /\\d+\\.\\d+/.test(text)) {
                return text;
            }
        }
    }
    
    // ── Fallback: Suche im gesamten Body-Text ──
    // WARUM? Wenn kein CSS-Selektor matcht (z.B. komplett neues UI).
    var bodyText = document.body.innerText;
    
    // Regex-Patterns für verschiedene Sprachen/Formate.
    // Reihenfolge: Spezifisch → Allgemein.
    var patterns = [
        /Guthaben[:\\s]*([€\\$]?\\s*[\\d,.]+)/i,   // Deutsch: "Guthaben: 12.35€"
        /Balance[:\\s]*([€\\$]?\\s*[\\d,.]+)/i,      // Englisch: "Balance: €12.35"
        /Points[:\\s]*([€\\$]?\\s*[\\d,.]+)/i,       // Englisch: "Points: 123"
        /Kontostand[:\\s]*([€\\$]?\\s*[\\d,.]+)/i,  // Deutsch: "Kontostand: 12.35"
        /([€\\$]\\s*[\\d,.]+)/i                     // Allgemein: "€ 12.35" (letzter Fallback)
    ];
    
    // Iteriere über alle Patterns.
    for (var pattern of patterns) {
        var match = bodyText.match(pattern);
        if (match) {
            return match[1];  // Gruppe 1 = der Betrag
        }
    }
    
    // Nichts gefunden → leerer String.
    return "";
})()
"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript ausführen
    # ═══════════════════════════════════════════════════════════════════════
    
    try:
        # Führe Balance-JavaScript im Browser aus.
        result = ws_eval(ws_url, balance_js, timeout=10)
        
        # Extrahiere Balance-String.
        balance_str = result.get("value", "") if result else ""
    
    except Exception as e:
        # Fehler beim Auslesen (z.B. JavaScript-Fehler, Timeout).
        logger.error(f"Balance read failed: {e}")
        
        return BalanceResponse(
            status="error",
            balance_eur=0.0,
            message=f"Balance read failed: {str(e)}",
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Balance parsen
    # ═══════════════════════════════════════════════════════════════════════
    
    balance_eur = 0.0
    
    if balance_str:
        # Entferne Währungssymbole und Whitespace.
        # WARUM? "12.35 €" → "12.35", "€12.35" → "12.35", " 12.35 " → "12.35".
        clean = balance_str.replace('€', '').replace('$', '').strip()
        
        # Ersetze Komma mit Punkt (deutsches Zahlenformat).
        # WARUM? "12,35" (Deutsch) → "12.35" (Python float).
        clean = clean.replace(',', '.')
        
        # Regex: Extrahiere Zahl (mit optionalen Dezimalstellen).
        match = re.search(r'(\d+[.,]?\d*)', clean)
        
        if match:
            try:
                # Konvertiere zu Float.
                balance_eur = float(match.group(1))
            except ValueError:
                # Sollte nicht passieren (Regex matcht nur Zahlen), aber sicherheitshalber.
                pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════
    
    return BalanceResponse(
        status="success",                           # Operation erfolgreich
        balance_eur=balance_eur,                     # Aktueller Kontostand
        currency="EUR",                              # Währung (ISO 4217)
        message=f"Balance: {balance_eur:.2f}€" if balance_eur > 0 else "Balance: 0.00€ (not visible)",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE VON DASHBOARD_ROUTES.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei implementiert 2 Dashboard-Endpoints:
#   1. POST /dashboard/scan   → Surveys mit € Rewards scannen (Heuristiken + Regex).
#   2. POST /dashboard/balance → Aktuellen Kontostand auslesen (mehrere Selektoren + Fallback).
#
# DESIGN-PRINZIPIEN:
#   1. CDP WebSocket: Direkte JavaScript-Ausführung (schneller als Playwright).
#   2. Heuristiken: Mehrere CSS-Selektoren + Fallback auf Text-Suche (robust gegen UI-Änderungen).
#   3. Regex: Flexible Zahlen-Extraktion (deutsches Format, verschiedene Währungen).
#   4. Fail-Closed: Bei Fehlern → Error-Response (nicht Crash).
#   5. Self-Documenting: Klare Response-Messages ("Found 5 surveys, total rewards: 3.50€").
#
# WICHTIGE HELFER (aus survey_actions.py):
#   - get_dashboard_ws(port) → Findet Dashboard-Tab via CDP /json API.
#   - ws_eval(ws_url, js) → Führt JS aus und gibt Resultat zurück.
#
# REGISTRIERUNG IN MAIN.PY:
#   from api.dashboard_routes import router as dashboard_router
#   app.include_router(dashboard_router)
# ═══════════════════════════════════════════════════════════════════════════════
