"""Partially revert runner.py: keep improvements, restore old opening block and _detect_completion_text."""
from pathlib import Path

p = Path("survey-cli/survey/runner.py")
text = p.read_text()

old_opening = '''        # 3. Open survey — IN-PAGE MODAL (preferred) or NEW TAB (fallback)
        opener = SurveyOpener(self.config.cdp_port, self.config.debug)
        open_result = opener.open(survey_id, provider, survey_url, dashboard_ws)
        if not open_result.target:
            result.error = open_result.error or "Failed to open survey"
            result.status = open_result.status or "error"
            if result.status == "screen_out":
                log_earnings(survey_id, provider, 0, "screen_out", 0)
            return result
        target = open_result.target
        tab_ws = target.ws_url
        tab_id = target.tab_id
        is_in_page = target.mode == "in_page"
        actual_url = target.actual_url

        # Post-tab-creation: provider + URL detection
        if is_in_page:
            actual_url = "heypiggy.com/dashboard"
            real_provider = provider
        else:
            real_provider = self._detect_provider(actual_url) if actual_url else provider
            if real_provider != provider and real_provider != "unknown":
                result.provider = real_provider
                provider = real_provider
                if self.config.debug:
                    print(f"[RUN] Real provider: {provider} ({actual_url[:60]})")'''

new_opening = '''        # 3. Open survey — IN-PAGE MODAL (preferred) or NEW TAB (fallback)
        is_in_page = (provider == "in_page_modal")
        tab_id = None  # Only set for new-tab flow
        
        # 3a. Pre-survey cleanup: close all stacked modals on dashboard
        if is_in_page and dashboard_ws:
            n_closed = self._pre_survey_cleanup(dashboard_ws)
            if self.config.debug and n_closed > 0:
                print(f"[CLEANUP] Closed {n_closed} stacked modals")
        
        # 3b. Capture tabs before clickSurvey() for new-tab detection
        tabs_before = set()
        if is_in_page:
            try:
                for p in chrome.find_bot_tabs(self.config.cdp_port):
                    tabs_before.add(p.get("id", ""))
            except Exception:
                pass
        
        if is_in_page:
            # In-page modal: click survey card on dashboard (no new tab!)
            tab_ws = self._click_survey_card(survey_id)
            if not tab_ws:
                result.error = "Failed to click survey card (in-page modal)"
                result.status = "error"
                return result
            time.sleep(self.config.wait_page_load)
            
            # Check if a new tab opened (Qualtrics sometimes opens new tab anyway)
            new_ws = self._find_new_tab_after_click(tabs_before)
            if new_ws:
                tab_ws = new_ws
                is_in_page = False  # It's actually a new tab!
                if self.config.debug:
                    print(f"[TAB] Survey opened in NEW tab (Qualtrics redirect)")
        else:
            # Legacy: open new browser tab via Target.createTarget
            tab_id = self._create_tab(dashboard_ws, survey_url)
            if not tab_id:
                result.error = "Failed to create browser tab"
                result.status = "error"
                return result

            # Wait for CPX redirect + handle redirect page + detect REAL provider
            tab_ws, actual_url = self._find_survey_tab_ws(tab_id)
            
            # Check for stuck loading pages
            if tab_ws:
                page_text = BatchExecutor.read_page_text(tab_ws, 500).lower()
                if any(s in page_text for s in ["loading", "just getting things ready", "won't be long"]):
                    if self.config.debug:
                        print("[RUN] Stuck on loading page — skipping")
                    self._close_tab(tab_id)
                    result.status = "screen_out"
                    result.error = "Survey stuck on loading page"
                    log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                    return result
            
            time.sleep(self.config.wait_page_load)
            
            # Handle CPX redirect page (if stuck on "Sie werden umgeleitet")
            tab_ws, actual_url = self._find_survey_tab_ws(tab_id)
            if tab_ws:
                page_text = BatchExecutor.read_page_text(tab_ws, 500).lower()
                # Detect ALL expired survey error pages
                if any(s in page_text for s in [
                    "no app id", "survey not available", "error - unable to start survey",
                    "survey closed", "link has expired", "survey has ended",
                    "leider ist ein fehler aufgetreten", "error occurred",
                    "this survey is no longer available", "survey unavailable",
                ]):
                    if self.config.debug:
                        print(f"[RUN] Survey URL expired or error page — skipping")
                    self._close_tab(tab_id)
                    result.status = "screen_out"
                    result.error = "Survey URL expired/error page"
                    log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                    return result
                if "umgeleitet" in page_text or "redirect" in page_text:
                    if self.config.debug:
                        print("[RUN] CPX redirect page — clicking link...")
                    self._click_redirect_link(tab_ws)
                    time.sleep(self.config.wait_page_load)

        # Post-tab-creation: provider + URL detection
        # For in-page modal: provider stays as "in_page_modal", URL is dashboard
        if is_in_page:
            actual_url = "heypiggy.com/dashboard"
            real_provider = provider
        else:
            # Detect real provider from actual URL
            real_provider = self._detect_provider(actual_url) if actual_url else provider
            if real_provider != provider and real_provider != "unknown":
                result.provider = real_provider
                provider = real_provider
                if self.config.debug:
                    print(f"[RUN] Real provider: {provider} ({actual_url[:60]})")'''

if old_opening in text:
    text = text.replace(old_opening, new_opening)
    print("Replaced opening block")
else:
    print("WARNING: old_opening not found")

# Revert _detect_completion_text replacements
text = text.replace(
    "(tool_detect(tab_ws) != \"running\")",
    "self._detect_completion_text(tab_ws)",
)
text = text.replace(
    "if ws_url and (tool_detect(ws_url) != \"running\"):",
    "if ws_url and self._detect_completion_text(ws_url):",
)

p.write_text(text)
print("Done")
