"""
HeyPiggy Survey Platform Connector - Production-ready integration.

Handles:
    - Login/authentication
    - Survey discovery and routing
    - Survey completion flow
    - Earnings tracking
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .browser_driver import BrowserDriver, ElementInfo
from .survey_parser import SurveyParser, ParsedSurvey, Question, QuestionType
from .answer_engine import AnswerEngine, Persona, Answer
from .captcha_solver import CaptchaSolver, CaptchaTask, CaptchaType
from .stealth import StealthBrowser, ProxyConfig

logger = logging.getLogger(__name__)


@dataclass
class HeyPiggySurvey:
    """HeyPiggy survey offer."""
    id: str
    title: str
    url: str
    reward_points: int
    estimated_minutes: int
    category: str = ""
    
    @property
    def reward_usd(self) -> float:
        """Convert points to USD (estimate: 100 points = $1)."""
        return self.reward_points / 100


@dataclass 
class HeyPiggyResult:
    """Result of HeyPiggy survey attempt."""
    survey_id: str
    status: str  # completed, disqualified, error
    points_earned: int = 0
    time_spent_seconds: int = 0
    error_message: str | None = None


class HeyPiggyConnector:
    """
    Production-ready HeyPiggy.com survey automation.
    
    Integrates all components:
    - StealthBrowser for anti-detection
    - BrowserDriver for automation
    - SurveyParser for question extraction
    - AnswerEngine for intelligent responses
    - CaptchaSolver for CAPTCHA handling
    """
    
    BASE_URL = "https://www.heypiggy.com"
    
    def __init__(
        self,
        persona: Persona,
        nvidia_local: bool = True,
        proxy: ProxyConfig | None = None,
        headless: bool = True,
    ):
        self.persona = persona
        self.captcha_api_key = captcha_api_key
        self.proxy = proxy
        self.headless = headless
        
        self._browser: BrowserDriver | None = None
        self._parser = SurveyParser()
        self._answer_engine = AnswerEngine(persona)
        self._captcha_solver: CaptchaSolver | None = None
        
        if captcha_api_key:
            self._captcha_solver = CaptchaSolver(
                use_local=nvidia_local,
                
            )
        
        self._logged_in = False
        self._session_stats = {
            "surveys_attempted": 0,
            "surveys_completed": 0,
            "surveys_disqualified": 0,
            "total_points": 0,
            "total_time_seconds": 0,
        }

    async def start(self) -> None:
        """Initialize browser and components."""
        self._browser = BrowserDriver(
            headless=self.headless,
            proxy=self.proxy,
        )
        await self._browser.start()
        logger.info("HeyPiggy connector started")

    async def stop(self) -> None:
        """Cleanup browser and resources."""
        if self._browser:
            await self._browser.stop()
        logger.info("HeyPiggy connector stopped")

    async def login(self, email: str, password: str) -> bool:
        """Login to HeyPiggy account."""
        if not self._browser:
            await self.start()
        
        try:
            await self._browser.goto(f"{self.BASE_URL}/login")
            await asyncio.sleep(2)
            
            # Fill login form with human-like typing
            email_input = await self._browser.find_element('input[name="email"], input[type="email"], #email')
            if email_input:
                await self._browser.human_type(email_input.selector, email)
            
            await asyncio.sleep(0.5)
            
            password_input = await self._browser.find_element('input[name="password"], input[type="password"], #password')
            if password_input:
                await self._browser.human_type(password_input.selector, password)
            
            await asyncio.sleep(0.5)
            
            # Handle potential CAPTCHA on login
            captcha_detected = await self._detect_captcha()
            if captcha_detected:
                solved = await self._solve_captcha()
                if not solved:
                    logger.error("Failed to solve login CAPTCHA")
                    return False
            
            # Click login button
            login_btn = await self._browser.find_element('button[type="submit"], input[type="submit"], .login-btn, #login-btn')
            if login_btn:
                await self._browser.human_click(login_btn.selector)
            
            # Wait for navigation
            await asyncio.sleep(3)
            await self._browser.wait_for_navigation()
            
            # Check if logged in
            current_url = await self._browser.get_url()
            if "dashboard" in current_url or "surveys" in current_url or "account" in current_url:
                self._logged_in = True
                logger.info("HeyPiggy login successful")
                return True
            
            # Check for error messages
            html = await self._browser.get_html()
            if "invalid" in html.lower() or "incorrect" in html.lower():
                logger.error("Invalid credentials")
                return False
            
            logger.warning("Login status unclear, assuming success")
            self._logged_in = True
            return True
            
        except Exception as e:
            logger.exception(f"Login error: {e}")
            return False

    async def get_available_surveys(self) -> list[HeyPiggySurvey]:
        """Get list of available surveys."""
        if not self._logged_in:
            logger.warning("Not logged in")
            return []
        
        surveys = []
        
        try:
            # Navigate to surveys page
            await self._browser.goto(f"{self.BASE_URL}/surveys")
            await asyncio.sleep(2)
            
            html = await self._browser.get_html()
            
            # Parse survey cards - adapt selectors to actual HeyPiggy structure
            survey_elements = await self._browser.find_elements(
                '.survey-card, .survey-item, [data-survey-id], .offer-card'
            )
            
            for elem in survey_elements:
                try:
                    # Extract survey data from element
                    survey_id = elem.attributes.get('data-survey-id', elem.attributes.get('data-id', ''))
                    if not survey_id:
                        # Try to extract from href
                        href = elem.attributes.get('href', '')
                        id_match = re.search(r'/survey/(\d+)', href)
                        if id_match:
                            survey_id = id_match.group(1)
                    
                    if not survey_id:
                        continue
                    
                    # Extract reward points
                    points_match = re.search(r'(\d+)\s*(?:points?|pts?)', elem.text, re.IGNORECASE)
                    points = int(points_match.group(1)) if points_match else 50
                    
                    # Extract time estimate
                    time_match = re.search(r'(\d+)\s*(?:min|minutes?)', elem.text, re.IGNORECASE)
                    est_minutes = int(time_match.group(1)) if time_match else 10
                    
                    surveys.append(HeyPiggySurvey(
                        id=survey_id,
                        title=elem.text[:100] if elem.text else f"Survey {survey_id}",
                        url=f"{self.BASE_URL}/survey/{survey_id}",
                        reward_points=points,
                        estimated_minutes=est_minutes,
                    ))
                    
                except Exception as e:
                    logger.debug(f"Error parsing survey element: {e}")
                    continue
            
            # Fallback: parse from HTML directly
            if not surveys:
                survey_pattern = r'href=["\']([^"\']*survey[^"\']*)["\'][^>]*>.*?(\d+)\s*(?:points?|pts?).*?(\d+)\s*min'
                for match in re.finditer(survey_pattern, html, re.IGNORECASE | re.DOTALL):
                    url = match.group(1)
                    if not url.startswith('http'):
                        url = self.BASE_URL + url
                    
                    surveys.append(HeyPiggySurvey(
                        id=re.search(r'/(\d+)', url).group(1) if re.search(r'/(\d+)', url) else str(len(surveys)),
                        title=f"Survey {len(surveys) + 1}",
                        url=url,
                        reward_points=int(match.group(2)),
                        estimated_minutes=int(match.group(3)),
                    ))
            
            logger.info(f"Found {len(surveys)} available surveys")
            
        except Exception as e:
            logger.exception(f"Error fetching surveys: {e}")
        
        return surveys

    async def complete_survey(self, survey: HeyPiggySurvey) -> HeyPiggyResult:
        """
        Complete a single survey end-to-end.
        
        This is the main automation flow:
        1. Navigate to survey
        2. Parse questions
        3. Generate answers
        4. Handle CAPTCHAs
        5. Submit and navigate pages
        6. Track completion
        """
        start_time = datetime.now()
        self._session_stats["surveys_attempted"] += 1
        
        try:
            logger.info(f"Starting survey: {survey.id} - {survey.title[:50]}")
            
            # Navigate to survey
            await self._browser.goto(survey.url)
            await asyncio.sleep(2)
            
            page_count = 0
            max_pages = 50  # Safety limit
            
            while page_count < max_pages:
                page_count += 1
                logger.info(f"Processing page {page_count}")
                
                # Check for CAPTCHA
                if await self._detect_captcha():
                    solved = await self._solve_captcha()
                    if not solved:
                        return HeyPiggyResult(
                            survey_id=survey.id,
                            status="error",
                            error_message="CAPTCHA solve failed",
                            time_spent_seconds=int((datetime.now() - start_time).total_seconds()),
                        )
                
                # Check for disqualification
                html = await self._browser.get_html()
                if self._is_disqualified(html):
                    self._session_stats["surveys_disqualified"] += 1
                    return HeyPiggyResult(
                        survey_id=survey.id,
                        status="disqualified",
                        time_spent_seconds=int((datetime.now() - start_time).total_seconds()),
                    )
                
                # Check for completion
                if self._is_completed(html):
                    time_spent = int((datetime.now() - start_time).total_seconds())
                    self._session_stats["surveys_completed"] += 1
                    self._session_stats["total_points"] += survey.reward_points
                    self._session_stats["total_time_seconds"] += time_spent
                    
                    logger.info(f"Survey completed! Points: {survey.reward_points}")
                    
                    return HeyPiggyResult(
                        survey_id=survey.id,
                        status="completed",
                        points_earned=survey.reward_points,
                        time_spent_seconds=time_spent,
                    )
                
                # Parse current page
                url = await self._browser.get_url()
                parsed = await self._parser.parse(html, url)
                
                if not parsed.current_page.questions:
                    # No questions found, try to find and click next/continue
                    clicked = await self._click_next_button()
                    if not clicked:
                        logger.warning("No questions and no next button found")
                        break
                    await asyncio.sleep(2)
                    continue
                
                # Generate and fill answers
                for question in parsed.current_page.questions:
                    answer = self._answer_engine.generate_answer(question)
                    await self._fill_answer(question, answer)
                    await asyncio.sleep(0.3 + 0.5 * (hash(question.id) % 100) / 100)
                
                # Click next/submit
                await asyncio.sleep(1)
                clicked = await self._click_next_button()
                
                if not clicked:
                    # Try submit button
                    clicked = await self._click_submit_button()
                
                if not clicked:
                    logger.warning("Could not find next/submit button")
                    break
                
                # Wait for page load
                await asyncio.sleep(2)
                await self._browser.wait_for_navigation()
            
            # If we get here without completion, something went wrong
            return HeyPiggyResult(
                survey_id=survey.id,
                status="error",
                error_message="Max pages reached or flow interrupted",
                time_spent_seconds=int((datetime.now() - start_time).total_seconds()),
            )
            
        except Exception as e:
            logger.exception(f"Survey error: {e}")
            return HeyPiggyResult(
                survey_id=survey.id,
                status="error",
                error_message=str(e),
                time_spent_seconds=int((datetime.now() - start_time).total_seconds()),
            )

    async def _fill_answer(self, question: Question, answer: Answer) -> bool:
        """Fill answer for a specific question."""
        try:
            if question.type == QuestionType.RADIO:
                # Find and click the matching radio button
                for opt in question.options:
                    if opt.value == answer.value:
                        selector = opt.element_selector or f'input[value="{opt.value}"]'
                        await self._browser.human_click(selector)
                        return True
                        
            elif question.type == QuestionType.CHECKBOX:
                # Click each selected checkbox
                values = answer.value if isinstance(answer.value, list) else [answer.value]
                for val in values:
                    for opt in question.options:
                        if opt.value == val:
                            selector = opt.element_selector or f'input[value="{val}"]'
                            await self._browser.check_checkbox(selector, True)
                            break
                return True
                
            elif question.type == QuestionType.DROPDOWN:
                selector = question.element_selector or f'select[name="{question.id}"]'
                await self._browser.select_option(selector, str(answer.value))
                return True
                
            elif question.type == QuestionType.OPEN_TEXT:
                selector = question.element_selector or f'textarea[name="{question.id}"], input[name="{question.id}"]'
                await self._browser.human_type(selector, str(answer.value))
                return True
                
            elif question.type == QuestionType.SLIDER:
                # Sliders are tricky - try to set value directly
                selector = question.element_selector or f'input[type="range"][name="{question.id}"]'
                await self._browser.evaluate(f'''
                    document.querySelector('{selector}').value = {answer.value};
                    document.querySelector('{selector}').dispatchEvent(new Event('input'));
                    document.querySelector('{selector}').dispatchEvent(new Event('change'));
                ''')
                return True
                
            elif question.type == QuestionType.MATRIX:
                # Matrix questions - click each row's selected column
                if isinstance(answer.value, dict):
                    for row, col_value in answer.value.items():
                        selector = f'input[name*="{row}"][value="{col_value}"]'
                        await self._browser.human_click(selector)
                        await asyncio.sleep(0.2)
                return True
                
            elif question.type == QuestionType.NUMBER:
                selector = question.element_selector or f'input[type="number"][name="{question.id}"]'
                await self._browser.human_type(selector, str(answer.value))
                return True
                
            elif question.type == QuestionType.DATE:
                selector = question.element_selector or f'input[type="date"][name="{question.id}"]'
                await self._browser.evaluate(f'''
                    document.querySelector('{selector}').value = '{answer.value}';
                ''')
                return True
            
            else:
                # Generic fallback - try to find input and fill
                selector = question.element_selector or f'[name="{question.id}"]'
                element = await self._browser.find_element(selector)
                if element:
                    if element.tag == 'select':
                        await self._browser.select_option(selector, str(answer.value))
                    else:
                        await self._browser.human_type(selector, str(answer.value))
                    return True
                    
        except Exception as e:
            logger.warning(f"Error filling answer for {question.id}: {e}")
        
        return False

    async def _detect_captcha(self) -> bool:
        """Detect if CAPTCHA is present on page."""
        html = await self._browser.get_html()
        
        captcha_indicators = [
            'g-recaptcha',
            'h-captcha',
            'data-sitekey',
            'captcha',
            'recaptcha',
            'hcaptcha',
            'funcaptcha',
        ]
        
        html_lower = html.lower()
        for indicator in captcha_indicators:
            if indicator in html_lower:
                logger.info(f"CAPTCHA detected: {indicator}")
                return True
        
        return False

    async def _solve_captcha(self) -> bool:
        """Solve detected CAPTCHA."""
        if not self._captcha_solver:
            logger.error("No CAPTCHA solver configured")
            return False
        
        try:
            html = await self._browser.get_html()
            url = await self._browser.get_url()
            
            # Detect CAPTCHA type and site key
            captcha_type = CaptchaType.RECAPTCHA_V2
            site_key = None
            
            # reCAPTCHA
            recaptcha_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if recaptcha_match:
                site_key = recaptcha_match.group(1)
                if 'recaptcha/api.js?render=' in html:
                    captcha_type = CaptchaType.RECAPTCHA_V3
            
            # hCaptcha
            if not site_key:
                hcaptcha_match = re.search(r'data-sitekey=["\']([^"\']+)["\'].*hcaptcha', html, re.IGNORECASE)
                if hcaptcha_match:
                    site_key = hcaptcha_match.group(1)
                    captcha_type = CaptchaType.HCAPTCHA
            
            if not site_key:
                logger.error("Could not extract CAPTCHA site key")
                return False
            
            # Create and solve task
            task = CaptchaTask(
                type=captcha_type,
                site_key=site_key,
                page_url=url,
            )
            
            result = await self._captcha_solver.solve(task)
            
            if not result.success:
                logger.error(f"CAPTCHA solve failed: {result.error}")
                return False
            
            # Inject solution
            if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
                await self._browser.evaluate(f'''
                    document.getElementById('g-recaptcha-response').innerHTML = '{result.token}';
                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                        Object.keys(___grecaptcha_cfg.clients).forEach(key => {{
                            const client = ___grecaptcha_cfg.clients[key];
                            if (client.W && client.W.W) {{
                                client.W.W.callback('{result.token}');
                            }}
                        }});
                    }}
                ''')
            elif captcha_type == CaptchaType.HCAPTCHA:
                await self._browser.evaluate(f'''
                    document.querySelector('[name="h-captcha-response"]').value = '{result.token}';
                    document.querySelector('[name="g-recaptcha-response"]').value = '{result.token}';
                ''')
            
            logger.info(f"CAPTCHA solved in {result.solve_time:.1f}s")
            return True
            
        except Exception as e:
            logger.exception(f"CAPTCHA solve error: {e}")
            return False

    async def _click_next_button(self) -> bool:
        """Find and click next/continue button."""
        next_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'input[value="Next"]',
            'input[value="Continue"]',
            '.next-btn',
            '.continue-btn',
            '#next',
            '#continue',
            'button[type="submit"]',
            '.btn-next',
            '.btn-continue',
            '[data-action="next"]',
        ]
        
        for selector in next_selectors:
            try:
                element = await self._browser.find_element(selector)
                if element and element.is_visible:
                    await self._browser.human_click(selector)
                    return True
            except Exception:
                continue
        
        return False

    async def _click_submit_button(self) -> bool:
        """Find and click submit/finish button."""
        submit_selectors = [
            'button:has-text("Submit")',
            'button:has-text("Finish")',
            'button:has-text("Complete")',
            'input[type="submit"]',
            '.submit-btn',
            '.finish-btn',
            '#submit',
            '#finish',
        ]
        
        for selector in submit_selectors:
            try:
                element = await self._browser.find_element(selector)
                if element and element.is_visible:
                    await self._browser.human_click(selector)
                    return True
            except Exception:
                continue
        
        return False

    def _is_disqualified(self, html: str) -> bool:
        """Check if survey shows disqualification."""
        dq_patterns = [
            r"sorry.*(?:don't|do not) qualify",
            r"not (?:a )?(?:good )?(?:fit|match)",
            r"disqualif",
            r"screen(?:ed)? out",
            r"quota.*full",
            r"survey.*(?:closed|ended|full)",
            r"thank you.*(?:but|however)",
            r"unfortunately",
        ]
        
        html_lower = html.lower()
        for pattern in dq_patterns:
            if re.search(pattern, html_lower):
                return True
        
        return False

    def _is_completed(self, html: str) -> bool:
        """Check if survey shows completion."""
        completion_patterns = [
            r"thank you.*complet",
            r"survey.*complet",
            r"you(?:'ve| have) (?:finished|completed)",
            r"points.*(?:credited|added|earned)",
            r"reward.*(?:credited|added)",
            r"success(?:fully)? completed",
            r"congratulations",
        ]
        
        html_lower = html.lower()
        for pattern in completion_patterns:
            if re.search(pattern, html_lower):
                return True
        
        return False

    def get_session_stats(self) -> dict:
        """Get current session statistics."""
        stats = self._session_stats.copy()
        
        if stats["surveys_attempted"] > 0:
            stats["completion_rate"] = stats["surveys_completed"] / stats["surveys_attempted"]
        else:
            stats["completion_rate"] = 0
        
        if stats["total_time_seconds"] > 0:
            stats["points_per_hour"] = (stats["total_points"] / stats["total_time_seconds"]) * 3600
            stats["usd_per_hour"] = stats["points_per_hour"] / 100
        else:
            stats["points_per_hour"] = 0
            stats["usd_per_hour"] = 0
        
        return stats


async def run_heypiggy_session(
    email: str,
    password: str,
    persona: Persona,
    nvidia_local: bool = True,
    max_surveys: int = 10,
    headless: bool = True,
) -> dict:
    """
    Run a complete HeyPiggy survey session.
    
    This is the main entry point for OpenCode CLI integration.
    """
    connector = HeyPiggyConnector(
        persona=persona,
        captcha_api_key=captcha_api_key,
        headless=headless,
    )
    
    try:
        await connector.start()
        
        # Login
        if not await connector.login(email, password):
            return {"error": "Login failed", "stats": connector.get_session_stats()}
        
        # Get surveys
        surveys = await connector.get_available_surveys()
        
        if not surveys:
            return {"error": "No surveys available", "stats": connector.get_session_stats()}
        
        # Sort by estimated hourly rate
        surveys.sort(key=lambda s: s.reward_points / max(s.estimated_minutes, 1), reverse=True)
        
        # Complete surveys
        results = []
        for survey in surveys[:max_surveys]:
            result = await connector.complete_survey(survey)
            results.append({
                "survey_id": result.survey_id,
                "status": result.status,
                "points": result.points_earned,
                "time_seconds": result.time_spent_seconds,
            })
            
            # Break if too many failures
            stats = connector.get_session_stats()
            if stats["surveys_disqualified"] >= 5 and stats["surveys_completed"] == 0:
                logger.warning("Too many disqualifications, stopping session")
                break
            
            # Small delay between surveys
            await asyncio.sleep(5)
        
        return {
            "results": results,
            "stats": connector.get_session_stats(),
        }
        
    finally:
        await connector.stop()
