"""
Survey Daemon - 24/7 LangGraph Survey Agent

Components:
    - SurveyAgentGraph: LangGraph StateGraph for survey flow
    - SurveyDaemon: macOS LaunchAgent daemon
    - SurveyParser: Universal survey parser
    - AnswerEngine: Intelligent answer generation
    - CaptchaSolver: Multi-provider captcha solving
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
from .cli import main as cli_main

__all__ = [
    "SurveyAgentGraph",
    "SurveyDaemon",
    "SurveyParser",
    "AnswerEngine",
    "CaptchaSolver",
    "CaptchaSolverQueue",
    "Question",
    "QuestionType",
    "ParsedSurvey",
    "Persona",
    "Answer",
    "CaptchaTask",
    "CaptchaResult",
    "CaptchaType",
    "install_launchagent",
    "uninstall_launchagent",
    "cli_main",
]

__version__ = "0.1.0"

