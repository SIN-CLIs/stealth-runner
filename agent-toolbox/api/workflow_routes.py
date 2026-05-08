"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Workflow Routes (High-Level Automation)            ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  High-Level Workflow-Endpunkte die MEHRERE Operationen in EINEM Call        ║
║  kombinieren. Für einfache Clients die nicht selbst Session-Prüfung,         ║
║  Cookie-Injektion, Dashboard-Scan, und Survey-Auswahl implementieren       ║
║  wollen.                                                                     ║
║                                                                              ║
║  ARCHITEKTUR:                                                               ║
║  ──────────────                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  POST /workflow/run-best                                            │    ║
║  │    1. Prüfe Session (cookies/verify)                                │    ║
║  │    2. Wenn nicht aktiv → injiziere Cookies (cookies/inject)       │    ║
║  │    3. Wenn immer noch nicht → session_expired                       │    ║
║  │    4. Scan Dashboard (dashboard/scan)                               │    ║
║  │    5. Wähle beste Survey (Strategie: reward/efficiency/duration)    │    ║
║  │    6. Klicke Survey Card (survey/click-card)                        │    ║
║  │    7. Gib Ergebnis zurück                                           │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  WARUM EIGENER ROUTER?                                                      ║
║  ──────────────────────                                                      ║
║  • Modularität: Workflow-Logik ist von einzelnen Aktionen getrennt.       ║
║  • Wiederverwendung: Kann in anderen Projekten importiert werden.          ║
║  • Einfachheit: Client macht EINEN Call statt 4-5 einzelnen.               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

import time
import logging
from typing import Optional

from fastapi import APIRouter, Depends

from core.rate_limiter import rate_limit_dependency
from api.schemas import (
    WorkflowRunBestRequest,
    WorkflowRunBestResponse,
    DashboardSurvey,
)

from core.browser_manager import get_browser_manager
from core.cookie_manager import get_cookie_manager

# Interne Router-Funktionen (wiederverwendet von anderen Routern).
# WARUM interne Imports? Wir rufen die Logik direkt auf (kein HTTP-Loopback).
from api.survey_actions import get_dashboard_ws, ws_eval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["Workflow"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Session-Prüfung und Cookie-Injektion
# ═══════════════════════════════════════════════════════════════════════════════


async def _ensure_session(cdp_port: int) -> tuple[bool, str]:
    """
    Stellt sicher dass eine HeyPiggy-Session aktiv ist.
    
    ABLAUF:
    1. Prüfe ob Browser läuft (BrowserManager.is_running).
    2. Hole Page (BrowserManager.get_page()).
    3. Prüfe Session (CookieManager.verify_session()).
    4. Wenn aktiv → return (True, "Session active").
    5. Wenn nicht aktiv → lade Cookies (CookieManager.load_cookies()).
    6. Injiziere Cookies (CookieManager.inject_cookies()).
    7. Prüfe Session erneut.
    8. Wenn aktiv → return (True, "Session restored via cookies").
    9. Wenn nicht → return (False, "Session expired, manual login required").
    
    WARUM interne Funktion?
    → Wiederverwendung: Wird von mehreren Workflow-Endpoints verwendet.
    → Kein HTTP-Loopback: Wir rufen die Methoden direkt auf (schneller).
    → Robuster: Kein Netzwerk-Overhead, keine Port-Konflikte.
    
    Args:
        cdp_port: CDP Port für Chrome.
    
    Returns:
        Tuple[bool, str]: (session_active, message).
        bool: True wenn Session aktiv (eingeloggt), False sonst.
        str: Status-Meldung für Logging/Response.
    """
    # BrowserManager holen (Singleton).
    browser_mgr = get_browser_manager()
    
    # Wenn Chrome nicht läuft → starten.
    if not browser_mgr.is_running:
        logger.info("Browser not running, starting...")
        await browser_mgr.start(cdp_port=cdp_port)
    
    # Page holen (automatischer Start/Reconnect).
    page = await browser_mgr.get_page()
    
    # CookieManager holen (Singleton).
    cookie_mgr = get_cookie_manager()
    
    # Session prüfen.
    is_active = await cookie_mgr.verify_session(page)
    
    if is_active:
        return True, "Session active"
    
    # Session nicht aktiv → Cookies laden und injizieren.
    logger.info("Session not active, trying cookie injection...")
    
    try:
        # Cookies aus Datei laden.
        cookies = cookie_mgr.load_cookies("heypiggy-cookies.json")
        
        # Hole BrowserContext (Cookies werden im Context injiziert).
        context = page.context
        
        # Cookies injizieren.
        injected = await cookie_mgr.inject_cookies(context, cookies)
        logger.info(f"Injected {injected} cookies")
        
        # Session erneut prüfen.
        is_active = await cookie_mgr.verify_session(page)
        
        if is_active:
            return True, f"Session restored via {injected} cookies"
        else:
            return False, "Session expired after cookie injection"
    
    except FileNotFoundError:
        return False, "No cookie file found (run POST /cookies/extract first)"
    
    except Exception as e:
        logger.error(f"Session restore failed: {e}")
        return False, f"Session restore failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Beste Survey auswählen
# ═══════════════════════════════════════════════════════════════════════════════


def _select_best_survey(
    surveys: list[DashboardSurvey],
    strategy: str,
    min_reward: float
) -> Optional[DashboardSurvey]:
    """
    Wählt die "beste" Survey aus einer Liste.
    
    STRATEGIEN:
    • "reward"      → Höchster Reward (€).
    • "efficiency"  → Bestes Reward/Dauer-Verhältnis (€/min).
    • "duration"    → Kürzeste Dauer (min).
    
    WARUM Strategy?
    → "reward": Lohnt sich für hohe Rewards (z.B. 0.46€).
    → "efficiency": Lohnt sich für beste Zeit/Reward-Balance.
      Beispiel: 0.46€/4min = 0.115€/min vs 0.14€/2min = 0.07€/min.
      → Erste ist effizienter (mehr € pro Minute).
    → "duration": Schnell fertig (für "nur eine Survey machen").
    
    WARUM min_reward?
    → Filtert niedrig bezahlte Surveys aus (z.B. 0.04€ für 1min).
    → Default 0.0 = kein Filter (alle Surveys).
    
    WARUM Optional?
    → Wenn keine Surveys verfügbar → None.
    → Wenn alle Surveys unter min_reward → None.
    
    Args:
        surveys: Liste von DashboardSurvey-Objekten.
        strategy: Auswahlstrategie ("reward", "efficiency", "duration").
        min_reward: Minimaler Reward in EUR (Filter).
    
    Returns:
        Optional[DashboardSurvey]: Beste Survey oder None.
    
    Example:
        best = _select_best_survey(surveys, "efficiency", 0.05)
        # → Survey mit bestem €/min Verhältnis und Reward >= 0.05€.
    """
    # Filtere nach min_reward.
    eligible = [s for s in surveys if s.reward_eur >= min_reward]
    
    if not eligible:
        return None
    
    if strategy == "reward":
        # Höchster Reward.
        return max(eligible, key=lambda s: s.reward_eur)
    
    elif strategy == "efficiency":
        # Bestes Reward/Dauer-Verhältnis.
        # WARUM duration_min or 999? Wenn Dauer None (unbekannt) → sehr ineffizient.
        return max(eligible, key=lambda s: s.reward_eur / (s.duration_min or 999))
    
    elif strategy == "duration":
        # Kürzeste Dauer.
        # WARUM duration_min or 999? Wenn Dauer None (unbekannt) → sehr lang.
        return min(eligible, key=lambda s: s.duration_min or 999)
    
    else:
        # Default: efficiency.
        return max(eligible, key=lambda s: s.reward_eur / (s.duration_min or 999))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /workflow/run-best
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/run-best", response_model=WorkflowRunBestResponse, dependencies=[Depends(rate_limit_dependency)])
async def run_best(req: WorkflowRunBestRequest):
    """
    Führt einen kompletten Workflow aus: Session-Check → Cookie-Injektion
    → Dashboard-Scan → Beste Survey auswählen → Card klicken.
    
    ABLAUF:
    1. Zeit-Messung starten.
    2. Stelle Session sicher (_ensure_session):
       a. Prüfe ob Session aktiv.
       b. Wenn nicht → injiziere Cookies.
       c. Wenn immer noch nicht → session_expired.
    3. Wenn Session nicht aktiv → Error-Response.
    4. Scan Dashboard (dashboard/scan intern):
       a. CDP-JS: Suche Balance und Survey-Cards.
       b. Parse Ergebnis (JSON).
    5. Wähle beste Survey (_select_best_survey):
       a. Filtere nach min_reward.
       b. Wende Strategie an (reward/efficiency/duration).
    6. Wenn keine Survey gefunden → "no_surveys" Response.
    7. Klicke Survey Card (survey/click-card intern):
       a. CDP-JS: Suche Card mit onclick="clickSurvey('ID')".
       b. Simuliere Click.
       c. Warte 2s (Modal öffnet sich).
       d. Lese Modal-Inhalt (Buttons).
    8. Berechne elapsed_time.
    9. Gib WorkflowRunBestResponse zurück.
    
    WARUM EIN Endpoint?
    → Einfacher Client: Ein Call statt 4-5 einzelnen.
    → Robuster: Session-Check + Cookie-Injektion automatisch.
    → Optimiert: Beste Survey wird automatisch ausgewählt.
    → Weniger Netzwerk-Overhead (kein HTTP-Loopback).
    
    WARUM nicht "run-one" Survey bis zum Ende?
    → Survey-Automation ist komplex (Fragen beantworten, Disqualifikation).
    → Dieser Endpoint macht nur den "Einstieg" (Card-Click + Modal).
    → Client kann danach /survey/modal und /survey/click-button verwenden.
    → Oder: Client ruft /survey/run-one für komplette Automation.
    
    WARUM interne Funktionen statt HTTP-Calls?
    → Schneller: Kein HTTP-Overhead (Loopback zu localhost:8889).
    → Robuster: Kein Port-Konflikt, kein Netzwerk-Fehler.
    → Einfacher: Direkte Methoden-Aufrufe (statt curl + JSON-Parsing).
    
    WARUM Balance in Response?
    → Monitoring: Wie viel Guthaben habe ich?
    → Entscheidung: Wenn Balance < 10€ → weitermachen?
    → Statistiken: Verdienst-Tracking.
    
    Args:
        req: WorkflowRunBestRequest
            - cdp_port: CDP Port (default: 8888).
            - max_reward_filter: Minimaler Reward (default: 0.0 = kein Filter).
            - strategy: Auswahlstrategie (default: "efficiency").
    
    Returns:
        WorkflowRunBestResponse:
            - status: "success", "no_surveys", "session_expired", "error".
            - session_active: War Session nach Cookie-Injektion aktiv?
            - balance_eur: Aktueller Kontostand.
            - surveys_found: Anzahl gefundener Surveys.
            - survey_selected: Ausgewählte Survey (oder None).
            - card_clicked: War Card-Click erfolgreich?
            - modal_buttons: Buttons im Modal (z.B. ["Umfrage starten", "Schließen"]).
            - message: Zusammenfassung.
            - elapsed_s: Gesamtdauer.
    
    Example:
        POST /workflow/run-best
        {"strategy": "efficiency", "max_reward_filter": 0.05}
        → {"status": "success", "session_active": true, "balance_eur": 2.23,
            "surveys_found": 12, "survey_selected": {"survey_id": "59499596", ...},
            "card_clicked": true, "modal_buttons": ["Umfrage starten", "Schließen"],
            "message": "Session active. Found 12 surveys. Selected 0.46€/4min survey.",
            "elapsed_s": 5.42}
    """
    start = time.time()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Session sicherstellen
    # ═══════════════════════════════════════════════════════════════════════
    
    session_ok, session_msg = await _ensure_session(req.cdp_port)
    
    if not session_ok:
        return WorkflowRunBestResponse(
            status="session_expired",
            session_active=False,
            message=f"Session expired: {session_msg}. Please login manually first.",
            elapsed_s=time.time() - start,
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Dashboard scannen
    # ═══════════════════════════════════════════════════════════════════════
    
    # Wir verwenden CDP-JS direkt (schneller als HTTP-Loopback).
    ws_url = get_dashboard_ws(req.cdp_port)
    
    if not ws_url:
        return WorkflowRunBestResponse(
            status="error",
            session_active=True,
            message="Dashboard not found (Chrome running but no HeyPiggy tab)",
            elapsed_s=time.time() - start,
        )
    
    # Balance-Scan JavaScript.
    balance_js = """
(function() {
    var selectors = ['.balance', '.points', '[class*="balance"]', '[class*="points"]', '[class*="guthaben"]'];
    for (var sel of selectors) {
        var els = document.querySelectorAll(sel);
        for (var el of els) {
            var text = el.textContent.trim();
            if (text.includes('€') || /\\d+\\.\\d+/.test(text)) return text;
        }
    }
    var bodyText = document.body.innerText;
    var m = bodyText.match(/(Guthaben|Balance)[:\\s]*([€\\$]?\\s*[\\d,.]+)/i);
    return m ? m[2] : "";
})()
"""
    
    # Survey-Scan JavaScript.
    scan_js = """
(function() {
    var results = {balance: "", surveys: []};
    var cards = document.querySelectorAll('[onclick*="clickSurvey"]');
    for (var i=0; i<cards.length; i++) {
        var card = cards[i];
        var onclick = card.getAttribute("onclick") || '';
        var idMatch = onclick.match(/clickSurvey\\('?(\\d+)'?\\)/);
        var surveyId = idMatch ? idMatch[1] : '';
        var parent = card.closest('div, li, tr, article') || card;
        var cardText = parent.textContent || '';
        var rewardMatch = cardText.match(/(\\d+[.,]?\\d*)\\s*€/);
        var reward = rewardMatch ? parseFloat(rewardMatch[1].replace(',', '.')) : 0;
        var durationMatch = cardText.match(/(\\d+)\\s*min/i);
        var duration = durationMatch ? parseInt(durationMatch[1]) : null;
        var titleMatch = cardText.match(/([^€\\n]+)(?=\\d+[.,]?\\d*\\s*€)/);
        var title = titleMatch ? titleMatch[1].trim().substring(0, 100) : '';
        if (surveyId && reward > 0) {
            results.surveys.push({id: surveyId, reward: reward, duration: duration, title: title});
        }
    }
    return JSON.stringify(results);
})()
"""
    
    # Führe beide Scans aus (multi-call).
    import json as json_module
    from api.survey_actions import ws_eval_multi
    
    scan_results = ws_eval_multi(ws_url, (balance_js, 1), (scan_js, 2))
    
    balance_str = ""
    surveys_data = []
    
    if len(scan_results) >= 2:
        # Balance ist String (oder leer).
        balance_result = scan_results[0]
        if isinstance(balance_result, str):
            balance_str = balance_result
        
        # Surveys ist JSON-String.
        surveys_result = scan_results[1]
        if isinstance(surveys_result, str):
            try:
                surveys_data = json_module.loads(surveys_result).get("surveys", [])
            except Exception:
                surveys_data = []
    
    # Balance parsen.
    import re
    balance_eur = 0.0
    if balance_str:
        clean = balance_str.replace('€', '').replace('$', '').strip().replace(',', '.')
        m = re.search(r'(\d+[.,]?\d*)', clean)
        if m:
            try:
                balance_eur = float(m.group(1))
            except ValueError:
                pass
    
 # Surveys in Pydantic-Modelle konvertieren.
    surveys = []
    for s in surveys_data:
        surveys.append(DashboardSurvey(
            survey_id=str(s.get("id", "")),
            reward_eur=s.get("reward", 0),
            duration_min=s.get("duration"),
            title=s.get("title", ""),
        ))
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: Beste Survey auswählen
    # ═══════════════════════════════════════════════════════════════════════
    
    best = _select_best_survey(surveys, req.strategy, req.max_reward_filter)
    
    if not best:
        return WorkflowRunBestResponse(
            status="no_surveys",
            session_active=True,
            balance_eur=balance_eur,
            surveys_found=len(surveys),
            message=f"Session active. Found {len(surveys)} surveys, but none match criteria (min_reward={req.max_reward_filter}€, strategy={req.strategy}).",
            elapsed_s=time.time() - start,
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Survey Card klicken
    # ═══════════════════════════════════════════════════════════════════════
    
    click_js = f"""
(function() {{
    var cards = document.querySelectorAll("[onclick*=clickSurvey]");
    for (var c of cards) {{
        var onclick = c.getAttribute("onclick");
        var m = onclick.match(/clickSurvey\\('?(\\d+)'?\\)/);
        if (m && m[1] === "{best.survey_id}") {{
            c.click();
            return "clicked:" + m[1];
        }}
    }}
    var first = document.querySelector("[onclick*=clickSurvey]");
    if (first) {{ first.click(); return "clicked_first"; }}
    return "not_found";
}})()
"""
    
    click_result = ws_eval(ws_url, click_js, timeout=10)
    clicked = click_result and "clicked" in (click_result.get("value", "") if isinstance(click_result, dict) else "")
    
    # Warte auf Modal.
    import time as time_module
    time_module.sleep(2)
    
    # Modal-Inhalt lesen.
    modal_js = """
(function() {
    var modal = document.querySelector(".modal.show, [class*='modal'][class*='show']");
    if (!modal) return JSON.stringify({visible: false});
    var buttons = [];
    modal.querySelectorAll("button, a[role='button']").forEach(function(b) {
        var t = (b.textContent || '').trim();
        if (t) buttons.push(t.substring(0, 80));
    });
    return JSON.stringify({visible: true, text: modal.innerText.substring(0, 500), buttons: buttons});
})()
"""
    
    modal_result = ws_eval(ws_url, modal_js, timeout=10)
    modal_data = {"visible": False, "buttons": []}
    
    if modal_result:
        try:
            val = modal_result.get("value", "{}") if isinstance(modal_result, dict) else "{}"
            modal_data = json_module.loads(val)
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════
    
    elapsed = time.time() - start
    
    return WorkflowRunBestResponse(
        status="success",
        session_active=True,
        balance_eur=balance_eur,
        surveys_found=len(surveys),
        survey_selected=best,
        card_clicked=bool(clicked),
        modal_buttons=modal_data.get("buttons", []),
        message=f"Session active ({session_msg}). Found {len(surveys)} surveys. Selected {best.reward_eur}€/{best.duration_min or '?'}min survey. Card clicked: {clicked}.",
        elapsed_s=elapsed,
    )
