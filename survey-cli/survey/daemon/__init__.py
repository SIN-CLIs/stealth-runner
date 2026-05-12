"""
Survey Daemon - 24/7 LangGraph Survey Agent

Components:
    - SurveyAgentGraph: LangGraph StateGraph for survey flow
    - SurveyDaemon: macOS LaunchAgent daemon
    - SurveyParser: Universal survey parser
    - AnswerEngine: Intelligent answer generation
    - CaptchaSolver: Multi-provider captcha solving
    - StealthBrowser: Anti-detection browser automation
    - BrowserDriver: Playwright-based stealth driver
    - CLI: OpenCode CLI integration
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
from .cli import main as cli_main

__all__ = [
    # Core
    "SurveyAgentGraph",
    "SurveyDaemon",
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

__version__ = "0.2.0"

