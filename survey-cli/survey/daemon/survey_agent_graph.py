"""
SurveyAgentGraph - Production-ready LangGraph StateGraph for survey automation.

Fully integrated with:
    - BrowserDriver for automation
    - SurveyParser for question extraction
    - AnswerEngine for intelligent responses
    - CaptchaSolver for CAPTCHA handling
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from .browser_driver import BrowserDriver
from .survey_parser import SurveyParser, Question, QuestionType
from .answer_engine import AnswerEngine, Persona, Answer
from .captcha_solver import CaptchaSolverQueue, CaptchaTask, CaptchaType

logger = logging.getLogger(__name__)


class SurveyStatus(str, Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    PARSING = "parsing"
    ANSWERING = "answering"
    SOLVING_CAPTCHA = "solving_captcha"
    SUBMITTING = "submitting"
    COMPLETED = "completed"
    DISQUALIFIED = "disqualified"
    FAILED = "failed"


class AgentState(TypedDict):
    """LangGraph state for survey agent."""
    survey_url: str
    survey_id: str
    current_page: int
    total_pages: int
    questions: list[dict]
    answers: list[dict]
    persona: dict
    captcha_required: bool
    captcha_solved: bool
    status: str
    error: str | None
    started_at: str
    completed_at: str | None
    earnings: float
    html_content: str
    page_url: str


class SurveyAgentGraph:
    """
    Production-ready LangGraph-based survey completion agent.
    
    Flow:
        navigate -> parse -> [solve_captcha] -> answer -> submit -> (loop or complete)
    """

    def __init__(
        self,
        persona: Persona,
        db_path: str | Path = "~/.survey_agent/state.db",
        captcha_api_key: str | None = None,
        headless: bool = True,
    ):
        self.persona = persona
        self.db_path = Path(db_path).expanduser()
        self.headless = headless
        
        # Initialize components
        self._browser: BrowserDriver | None = None
        self._parser = SurveyParser()
        self._answer_engine = AnswerEngine(persona, db_path=self.db_path.parent / "answers.db")
        self._captcha_solver: CaptchaSolverQueue | None = None
        
        if captcha_api_key:
            self._captcha_solver = CaptchaSolverQueue(
                primary_provider="2captcha",
                primary_api_key=captcha_api_key,
            )
        
        self._init_db()
        self.graph = self._build_graph()

    def _init_db(self) -> None:
        """Initialize SQLite database for state persistence."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS survey_sessions (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT,
                started_at TEXT,
                completed_at TEXT,
                earnings REAL DEFAULT 0,
                error TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("navigate", self._navigate)
        graph.add_node("parse", self._parse)
        graph.add_node("check_status", self._check_status)
        graph.add_node("solve_captcha", self._solve_captcha)
        graph.add_node("answer", self._answer)
        graph.add_node("submit", self._submit)
        graph.add_node("complete", self._complete)
        graph.add_node("handle_error", self._handle_error)

        # Set entry point
        graph.set_entry_point("navigate")

        # Add edges
        graph.add_edge("navigate", "parse")
        graph.add_edge("parse", "check_status")
        
        graph.add_conditional_edges(
            "check_status",
            self._route_after_check,
            {
                "captcha": "solve_captcha",
                "answer": "answer",
                "complete": "complete",
                "disqualified": "handle_error",
                "error": "handle_error",
            }
        )
        
        graph.add_edge("solve_captcha", "parse")
        graph.add_edge("answer", "submit")
        
        graph.add_conditional_edges(
            "submit",
            self._route_after_submit,
            {
                "next_page": "parse",
                "complete": "complete",
                "error": "handle_error",
            }
        )
        
        graph.add_edge("complete", END)
        graph.add_edge("handle_error", END)

        return graph.compile()

    async def _navigate(self, state: AgentState) -> AgentState:
        """Navigate to survey URL."""
        logger.info(f"Navigating to: {state['survey_url']}")
        state["status"] = SurveyStatus.NAVIGATING.value
        state["started_at"] = datetime.utcnow().isoformat()
        
        if not self._browser:
            self._browser = BrowserDriver(headless=self.headless)
            await self._browser.start()
        
        await self._browser.goto(state["survey_url"])
        await asyncio.sleep(2)
        
        state["html_content"] = await self._browser.get_html()
        state["page_url"] = await self._browser.get_url()
        
        return state

    async def _parse(self, state: AgentState) -> AgentState:
        """Parse current page for questions."""
        logger.info(f"Parsing page {state['current_page']}")
        state["status"] = SurveyStatus.PARSING.value
        
        # Get fresh HTML
        state["html_content"] = await self._browser.get_html()
        state["page_url"] = await self._browser.get_url()
        
        # Parse survey
        parsed = await self._parser.parse(state["html_content"], state["page_url"])
        
        state["questions"] = [
            {
                "id": q.id,
                "type": q.type.value,
                "text": q.text,
                "options": [{"value": o.value, "label": o.label} for o in q.options],
                "required": q.required,
                "selector": q.element_selector,
            }
            for q in parsed.current_page.questions
        ]
        
        state["captcha_required"] = parsed.captcha_detected
        state["total_pages"] = max(state["total_pages"], parsed.total_pages)
        
        logger.info(f"Found {len(state['questions'])} questions, captcha: {state['captcha_required']}")
        
        return state

    async def _check_status(self, state: AgentState) -> AgentState:
        """Check page status (captcha, DQ, completion)."""
        html = state["html_content"].lower()
        
        # Check for disqualification
        dq_patterns = ["don't qualify", "do not qualify", "disqualified", "screened out", "quota full"]
        for pattern in dq_patterns:
            if pattern in html:
                state["status"] = SurveyStatus.DISQUALIFIED.value
                state["error"] = "Survey disqualification"
                return state
        
        # Check for completion
        complete_patterns = ["thank you for completing", "survey completed", "successfully completed", "points credited"]
        for pattern in complete_patterns:
            if pattern in html:
                state["status"] = SurveyStatus.COMPLETED.value
                state["completed_at"] = datetime.utcnow().isoformat()
                return state
        
        # Check for captcha
        if state["captcha_required"] and not state["captcha_solved"]:
            state["status"] = SurveyStatus.SOLVING_CAPTCHA.value
            return state
        
        # Ready to answer
        state["status"] = SurveyStatus.ANSWERING.value
        return state

    def _route_after_check(self, state: AgentState) -> str:
        """Route based on status check."""
        status = state["status"]
        
        if status == SurveyStatus.SOLVING_CAPTCHA.value:
            return "captcha"
        elif status == SurveyStatus.COMPLETED.value:
            return "complete"
        elif status == SurveyStatus.DISQUALIFIED.value:
            return "disqualified"
        elif status == SurveyStatus.FAILED.value:
            return "error"
        else:
            return "answer"

    async def _solve_captcha(self, state: AgentState) -> AgentState:
        """Solve CAPTCHA on page."""
        logger.info("Solving CAPTCHA")
        
        if not self._captcha_solver:
            state["error"] = "No CAPTCHA solver configured"
            state["status"] = SurveyStatus.FAILED.value
            return state
        
        import re
        html = state["html_content"]
        
        # Extract site key
        site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if not site_key_match:
            state["error"] = "Could not find CAPTCHA site key"
            state["status"] = SurveyStatus.FAILED.value
            return state
        
        site_key = site_key_match.group(1)
        captcha_type = CaptchaType.HCAPTCHA if "hcaptcha" in html.lower() else CaptchaType.RECAPTCHA_V2
        
        task = CaptchaTask(
            type=captcha_type,
            site_key=site_key,
            page_url=state["page_url"],
        )
        
        result = await self._captcha_solver.solve(task)
        
        if not result.success:
            state["error"] = f"CAPTCHA solve failed: {result.error}"
            state["status"] = SurveyStatus.FAILED.value
            return state
        
        # Inject token
        if captcha_type == CaptchaType.RECAPTCHA_V2:
            await self._browser.evaluate(f'''
                document.getElementById('g-recaptcha-response').innerHTML = '{result.token}';
            ''')
        else:
            await self._browser.evaluate(f'''
                document.querySelector('[name="h-captcha-response"]').value = '{result.token}';
            ''')
        
        state["captcha_solved"] = True
        logger.info(f"CAPTCHA solved in {result.solve_time:.1f}s")
        
        return state

    async def _answer(self, state: AgentState) -> AgentState:
        """Generate and fill answers for all questions."""
        logger.info(f"Answering {len(state['questions'])} questions")
        state["status"] = SurveyStatus.ANSWERING.value
        
        for q_data in state["questions"]:
            # Reconstruct Question object
            from .survey_parser import QuestionOption
            question = Question(
                id=q_data["id"],
                type=QuestionType(q_data["type"]),
                text=q_data["text"],
                options=[QuestionOption(value=o["value"], label=o["label"]) for o in q_data["options"]],
                required=q_data["required"],
                element_selector=q_data.get("selector"),
            )
            
            # Generate answer
            answer = self._answer_engine.generate_answer(question)
            
            # Store answer
            state["answers"].append({
                "question_id": question.id,
                "value": answer.value,
                "confidence": answer.confidence,
            })
            
            # Fill answer in browser
            await self._fill_answer(question, answer)
            await asyncio.sleep(0.3 + 0.4 * (hash(question.id) % 100) / 100)
        
        return state

    async def _fill_answer(self, question: Question, answer: Answer) -> None:
        """Fill a single answer in the browser."""
        try:
            if question.type == QuestionType.RADIO:
                for opt in question.options:
                    if opt.value == answer.value:
                        selector = f'input[value="{opt.value}"]'
                        await self._browser.human_click(selector)
                        break
                        
            elif question.type == QuestionType.CHECKBOX:
                values = answer.value if isinstance(answer.value, list) else [answer.value]
                for val in values:
                    selector = f'input[value="{val}"]'
                    await self._browser.check_checkbox(selector, True)
                    
            elif question.type == QuestionType.DROPDOWN:
                selector = question.element_selector or f'select[name="{question.id}"]'
                await self._browser.select_option(selector, str(answer.value))
                
            elif question.type == QuestionType.OPEN_TEXT:
                selector = question.element_selector or f'textarea, input[type="text"]'
                await self._browser.human_type(selector, str(answer.value))
                
            elif question.type == QuestionType.SLIDER:
                selector = question.element_selector or 'input[type="range"]'
                await self._browser.evaluate(f'''
                    const el = document.querySelector('{selector}');
                    if (el) {{ el.value = {answer.value}; el.dispatchEvent(new Event('change')); }}
                ''')
                
            elif question.type == QuestionType.NUMBER:
                selector = question.element_selector or 'input[type="number"]'
                await self._browser.human_type(selector, str(answer.value))
                
        except Exception as e:
            logger.warning(f"Error filling answer for {question.id}: {e}")

    async def _submit(self, state: AgentState) -> AgentState:
        """Submit current page and navigate."""
        logger.info("Submitting page")
        state["status"] = SurveyStatus.SUBMITTING.value
        
        # Try next/submit buttons
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            '.next-btn', '.continue-btn', '.submit-btn',
            '#next', '#continue', '#submit',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Submit")',
        ]
        
        clicked = False
        for selector in submit_selectors:
            try:
                element = await self._browser.find_element(selector)
                if element and element.is_visible:
                    await self._browser.human_click(selector)
                    clicked = True
                    break
            except Exception:
                continue
        
        if not clicked:
            # Try pressing Enter as last resort
            await self._browser.evaluate("document.activeElement.form?.submit()")
        
        # Wait for navigation
        await asyncio.sleep(2)
        await self._browser.wait_for_navigation()
        
        state["current_page"] += 1
        state["html_content"] = await self._browser.get_html()
        state["page_url"] = await self._browser.get_url()
        
        return state

    def _route_after_submit(self, state: AgentState) -> str:
        """Route after page submission."""
        html = state["html_content"].lower()
        
        # Check completion
        if any(p in html for p in ["thank you", "completed", "success", "finished"]):
            return "complete"
        
        # Check for errors
        if state.get("error"):
            return "error"
        
        # Safety limit
        if state["current_page"] > 50:
            state["error"] = "Max pages exceeded"
            return "error"
        
        return "next_page"

    async def _complete(self, state: AgentState) -> AgentState:
        """Handle successful completion."""
        logger.info("Survey completed successfully")
        state["status"] = SurveyStatus.COMPLETED.value
        state["completed_at"] = datetime.utcnow().isoformat()
        
        self._save_state(state)
        
        return state

    async def _handle_error(self, state: AgentState) -> AgentState:
        """Handle errors and disqualification."""
        logger.warning(f"Survey ended: {state['status']} - {state.get('error')}")
        
        if state["status"] != SurveyStatus.DISQUALIFIED.value:
            state["status"] = SurveyStatus.FAILED.value
        
        self._save_state(state)
        
        return state

    def _save_state(self, state: AgentState) -> None:
        """Persist state to SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO survey_sessions 
            (id, url, status, state_json, started_at, completed_at, earnings, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state["survey_id"],
            state["survey_url"],
            state["status"],
            json.dumps({k: v for k, v in state.items() if k != "html_content"}),
            state["started_at"],
            state.get("completed_at"),
            state.get("earnings", 0),
            state.get("error"),
        ))
        conn.commit()
        conn.close()

    async def run(self, survey_url: str) -> AgentState:
        """Run the survey completion graph."""
        import uuid
        
        initial_state: AgentState = {
            "survey_url": survey_url,
            "survey_id": str(uuid.uuid4()),
            "current_page": 1,
            "total_pages": 1,
            "questions": [],
            "answers": [],
            "persona": self.persona.to_dict(),
            "captcha_required": False,
            "captcha_solved": False,
            "status": SurveyStatus.IDLE.value,
            "error": None,
            "started_at": "",
            "completed_at": None,
            "earnings": 0.0,
            "html_content": "",
            "page_url": "",
        }

        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        finally:
            if self._browser:
                await self._browser.stop()
                self._browser = None

    def get_stats(self) -> dict:
        """Get completion statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'disqualified' THEN 1 ELSE 0 END) as disqualified,
                SUM(earnings) as total_earnings
            FROM survey_sessions
        """)
        row = cursor.fetchone()
        conn.close()
        
        return {
            "total_surveys": row[0] or 0,
            "completed": row[1] or 0,
            "failed": row[2] or 0,
            "disqualified": row[3] or 0,
            "total_earnings": row[4] or 0,
            "completion_rate": (row[1] or 0) / row[0] if row[0] else 0,
        }
