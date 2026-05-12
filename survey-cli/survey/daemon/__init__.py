"""
Survey Daemon - Production-Ready 24/7 Survey Automation Agent

Core Components:
    - SurveyAgentGraph: LangGraph StateGraph for survey flow
    - HeyPiggyConnector: HeyPiggy.com platform integration
    - SurveyParser: Universal survey parser
    - AnswerEngine: Intelligent persona-based answers
    - CaptchaSolver: Multi-provider captcha solving
    - StealthBrowser: Anti-detection browser automation
    - BrowserDriver: Playwright-based stealth driver
    - SurveyDaemon: macOS LaunchAgent daemon
"""

from .survey_agent_graph import SurveyAgentGraph
from .survey_daemon import SurveyDaemon, install_launchagent, uninstall_launchagent
from .survey_parser import SurveyParser, Question, QuestionType, ParsedSurvey
from .answer_engine import AnswerEngine, Persona, Answer
from .captcha_solver import (
    CaptchaSolver,
    CaptchaSolverQueue,
    CaptchaTask,
    CaptchaResult,
    CaptchaType,
)
from .stealth import (
    StealthBrowser,
    FingerprintGenerator,
    Fingerprint,
    MouseSimulator,
    TypingSimulator,
    SessionManager,
    ProxyRotator,
    ProxyConfig,
)
from .browser_driver import BrowserDriver, ElementInfo
from .heypiggy import HeyPiggyConnector, HeyPiggySurvey, HeyPiggyResult, run_heypiggy_session
from .cli import main as cli_main

__all__ = [
    # Core Graph
    "SurveyAgentGraph",
    "SurveyDaemon",
    # HeyPiggy
    "HeyPiggyConnector",
    "HeyPiggySurvey",
    "HeyPiggyResult",
    "run_heypiggy_session",
    # Parsing
    "SurveyParser",
    "Question",
    "QuestionType",
    "ParsedSurvey",
    # Answers
    "AnswerEngine",
    "Persona",
    "Answer",
    # Captcha
    "CaptchaSolver",
    "CaptchaSolverQueue",
    "CaptchaTask",
    "CaptchaResult",
    "CaptchaType",
    # Stealth
    "StealthBrowser",
    "FingerprintGenerator",
    "Fingerprint",
    "MouseSimulator",
    "TypingSimulator",
    "SessionManager",
    "ProxyRotator",
    "ProxyConfig",
    # Browser
    "BrowserDriver",
    "ElementInfo",
    # CLI
    "install_launchagent",
    "uninstall_launchagent",
    "cli_main",
]

__version__ = "1.0.0"
