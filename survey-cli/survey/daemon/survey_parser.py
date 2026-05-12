"""
Universal Survey Parser - Extracts questions from any survey platform.

Supports:
    - Qualtrics
    - SurveyMonkey
    - Google Forms
    - TypeForm
    - Generic HTML forms

Question Types:
    - Radio buttons
    - Checkboxes
    - Sliders/Ranges
    - Matrix/Grid
    - Open text
    - Ranking/Drag-drop
    - Dropdowns
    - Date pickers
    - Number inputs
"""

# ruff: noqa: E501  # CSS selectors / argparse help / log strings — wrapping changes semantics
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QuestionType(str, Enum):
    """Supported survey question types."""

    RADIO = "radio"
    CHECKBOX = "checkbox"
    SLIDER = "slider"
    MATRIX = "matrix"
    OPEN_TEXT = "open_text"
    RANKING = "ranking"
    DROPDOWN = "dropdown"
    DATE = "date"
    NUMBER = "number"
    LIKERT = "likert"
    NPS = "nps"
    FILE_UPLOAD = "file_upload"
    UNKNOWN = "unknown"


@dataclass
class QuestionOption:
    """Single answer option for a question."""

    value: str
    label: str
    element_id: str | None = None
    element_selector: str | None = None


@dataclass
class Question:
    """Parsed survey question."""

    id: str
    type: QuestionType
    text: str
    options: list[QuestionOption] = field(default_factory=list)
    required: bool = True
    validation: dict[str, Any] = field(default_factory=dict)
    element_selector: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    rows: list[str] = field(default_factory=list)  # For matrix questions
    columns: list[str] = field(default_factory=list)  # For matrix questions


@dataclass
class SurveyPage:
    """Single page of a multi-page survey."""

    page_number: int
    questions: list[Question]
    has_next: bool
    next_button_selector: str | None = None
    submit_button_selector: str | None = None


@dataclass
class ParsedSurvey:
    """Complete parsed survey structure."""

    url: str
    title: str
    platform: str
    total_pages: int
    current_page: SurveyPage
    captcha_detected: bool = False
    captcha_type: str | None = None
    captcha_site_key: str | None = None


class SurveyParser:
    """
    Universal survey parser that works across platforms.

    Uses DOM analysis to detect question types and extract
    answer options, validation rules, and navigation elements.
    """

    # Platform detection patterns
    PLATFORM_PATTERNS = {
        "qualtrics": [
            r"qualtrics\.com",
            r"class=\"QuestionText\"",
            r"QID\d+",
        ],
        "surveymonkey": [
            r"surveymonkey\.com",
            r"class=\"question-body\"",
            r"data-question-id",
        ],
        "google_forms": [
            r"docs\.google\.com/forms",
            r"class=\"freebirdFormviewerViewItemsItemItem\"",
        ],
        "typeform": [
            r"typeform\.com",
            r"data-qa=\"question\"",
        ],
    }

    # Question type detection patterns
    QUESTION_PATTERNS = {
        QuestionType.RADIO: [
            r"input\[type=[\"']radio[\"']\]",
            r"role=[\"']radiogroup[\"']",
            r"class=.*radio.*",
        ],
        QuestionType.CHECKBOX: [
            r"input\[type=[\"']checkbox[\"']\]",
            r"role=[\"']checkbox[\"']",
            r"class=.*checkbox.*",
        ],
        QuestionType.SLIDER: [
            r"input\[type=[\"']range[\"']\]",
            r"role=[\"']slider[\"']",
            r"class=.*slider.*",
        ],
        QuestionType.DROPDOWN: [
            r"<select",
            r"role=[\"']listbox[\"']",
            r"class=.*dropdown.*",
        ],
        QuestionType.OPEN_TEXT: [
            r"<textarea",
            r"input\[type=[\"']text[\"']\]",
            r"contenteditable=[\"']true[\"']",
        ],
        QuestionType.MATRIX: [
            r"class=.*matrix.*",
            r"class=.*grid.*",
            r"role=[\"']grid[\"']",
        ],
        QuestionType.DATE: [
            r"input\[type=[\"']date[\"']\]",
            r"class=.*datepicker.*",
        ],
        QuestionType.NUMBER: [
            r"input\[type=[\"']number[\"']\]",
            r"inputmode=[\"']numeric[\"']",
        ],
    }

    # Captcha detection patterns
    CAPTCHA_PATTERNS = {
        "recaptcha_v2": [
            r"g-recaptcha",
            r"grecaptcha\.render",
            r"data-sitekey",
        ],
        "recaptcha_v3": [
            r"grecaptcha\.execute",
            r"recaptcha/api\.js\?render=",
        ],
        "hcaptcha": [
            r"h-captcha",
            r"hcaptcha\.com",
            r"data-sitekey.*hcaptcha",
        ],
        "funcaptcha": [
            r"funcaptcha",
            r"arkoselabs\.com",
        ],
    }

    def __init__(self):
        self._platform_cache: dict[str, str] = {}

    async def parse(self, html: str, url: str) -> ParsedSurvey:
        """
        Parse survey HTML and extract all questions.

        Args:
            html: Raw HTML content of the survey page
            url: URL of the survey

        Returns:
            ParsedSurvey with extracted questions and metadata
        """
        platform = self._detect_platform(html, url)
        title = self._extract_title(html)
        captcha_info = self._detect_captcha(html)

        questions = await self._extract_questions(html, platform)
        navigation = self._extract_navigation(html, platform)

        page = SurveyPage(
            page_number=1,
            questions=questions,
            has_next=navigation["has_next"],
            next_button_selector=navigation["next_selector"],
            submit_button_selector=navigation["submit_selector"],
        )

        return ParsedSurvey(
            url=url,
            title=title,
            platform=platform,
            total_pages=navigation["total_pages"],
            current_page=page,
            captcha_detected=captcha_info["detected"],
            captcha_type=captcha_info["type"],
            captcha_site_key=captcha_info["site_key"],
        )

    def _detect_platform(self, html: str, url: str) -> str:
        """Detect survey platform from HTML and URL."""
        # Check cache
        if url in self._platform_cache:
            return self._platform_cache[url]

        combined = html + url

        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    self._platform_cache[url] = platform
                    logger.info(f"Detected platform: {platform}")
                    return platform

        return "generic"

    def _extract_title(self, html: str) -> str:
        """Extract survey title from HTML."""
        # Try common title patterns
        patterns = [
            r"<title>([^<]+)</title>",
            r"<h1[^>]*>([^<]+)</h1>",
            r"class=[\"']survey-title[\"'][^>]*>([^<]+)<",
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Untitled Survey"

    def _detect_captcha(self, html: str) -> dict[str, Any]:
        """Detect captcha presence and type."""
        result = {
            "detected": False,
            "type": None,
            "site_key": None,
        }

        for captcha_type, patterns in self.CAPTCHA_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    result["detected"] = True
                    result["type"] = captcha_type

                    # Extract site key
                    site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
                    if site_key_match:
                        result["site_key"] = site_key_match.group(1)

                    logger.info(f"Captcha detected: {captcha_type}")
                    return result

        return result

    async def _extract_questions(self, html: str, platform: str) -> list[Question]:
        """Extract all questions from HTML."""
        questions = []

        # Platform-specific extraction
        if platform == "qualtrics":
            questions = self._extract_qualtrics_questions(html)
        elif platform == "surveymonkey":
            questions = self._extract_surveymonkey_questions(html)
        elif platform == "google_forms":
            questions = self._extract_google_forms_questions(html)
        else:
            questions = self._extract_generic_questions(html)

        logger.info(f"Extracted {len(questions)} questions")
        return questions

    def _extract_qualtrics_questions(self, html: str) -> list[Question]:
        """Extract questions from Qualtrics survey."""
        questions = []

        # Find question containers
        question_pattern = r'id="(QID\d+)"[^>]*class="[^"]*QuestionOuter[^"]*"'
        question_matches = re.finditer(question_pattern, html)

        for match in question_matches:
            qid = match.group(1)

            # Extract question text
            text_pattern = rf'{qid}[^>]*>.*?class="QuestionText[^"]*"[^>]*>([^<]+)<'
            text_match = re.search(text_pattern, html, re.DOTALL)
            text = text_match.group(1).strip() if text_match else ""

            # Detect question type
            qtype = self._detect_question_type(html, qid)

            # Extract options
            options = self._extract_options(html, qid, qtype)

            questions.append(
                Question(
                    id=qid,
                    type=qtype,
                    text=text,
                    options=options,
                    element_selector=f"#{qid}",
                )
            )

        return questions

    def _extract_surveymonkey_questions(self, html: str) -> list[Question]:
        """Extract questions from SurveyMonkey survey."""
        questions = []

        # Find question containers
        pattern = r'data-question-id="(\d+)"'
        for match in re.finditer(pattern, html):
            qid = f"q_{match.group(1)}"

            # Extract question context around the match
            start = max(0, match.start() - 2000)
            end = min(len(html), match.end() + 2000)
            context = html[start:end]

            # Extract text
            text_match = re.search(r'class="question-title[^"]*"[^>]*>([^<]+)<', context)
            text = text_match.group(1).strip() if text_match else ""

            qtype = self._detect_question_type(context, qid)
            options = self._extract_options(context, qid, qtype)

            questions.append(
                Question(
                    id=qid,
                    type=qtype,
                    text=text,
                    options=options,
                )
            )

        return questions

    def _extract_google_forms_questions(self, html: str) -> list[Question]:
        """Extract questions from Google Forms."""
        questions = []

        # Google Forms uses data attributes
        pattern = r'data-params="([^"]+)"'

        for i, match in enumerate(re.finditer(pattern, html)):
            try:
                params = match.group(1)
                # Decode HTML entities
                params = params.replace("&quot;", '"')

                qid = f"gf_{i}"

                # Extract text from nearby elements
                start = max(0, match.start() - 1000)
                context = html[start : match.end()]

                text_match = re.search(
                    r'class="[^"]*freebirdFormviewerComponentsQuestionBaseTitle[^"]*"[^>]*>([^<]+)<',
                    context,
                )
                text = text_match.group(1).strip() if text_match else f"Question {i + 1}"

                qtype = self._detect_question_type(context, qid)
                options = self._extract_options(context, qid, qtype)

                questions.append(
                    Question(
                        id=qid,
                        type=qtype,
                        text=text,
                        options=options,
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing Google Forms question: {e}")

        return questions

    def _extract_generic_questions(self, html: str) -> list[Question]:
        """Extract questions from generic HTML form."""
        questions = []

        # Find form elements
        form_elements = [
            (r'<input[^>]+type=["\']radio["\'][^>]*>', QuestionType.RADIO),
            (r'<input[^>]+type=["\']checkbox["\'][^>]*>', QuestionType.CHECKBOX),
            (r"<select[^>]*>.*?</select>", QuestionType.DROPDOWN),
            (r"<textarea[^>]*>", QuestionType.OPEN_TEXT),
            (r'<input[^>]+type=["\']range["\'][^>]*>', QuestionType.SLIDER),
            (r'<input[^>]+type=["\']number["\'][^>]*>', QuestionType.NUMBER),
            (r'<input[^>]+type=["\']date["\'][^>]*>', QuestionType.DATE),
            (r'<input[^>]+type=["\']text["\'][^>]*>', QuestionType.OPEN_TEXT),
        ]

        seen_names = set()

        for pattern, qtype in form_elements:
            for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
                element = match.group(0)

                # Extract name attribute
                name_match = re.search(r'name=["\']([^"\']+)["\']', element)
                if not name_match:
                    continue

                name = name_match.group(1)
                if name in seen_names:
                    continue
                seen_names.add(name)

                # Find associated label
                label_match = re.search(
                    rf'<label[^>]*for=["\']?{re.escape(name)}["\']?[^>]*>([^<]+)<',
                    html,
                    re.IGNORECASE,
                )
                text = label_match.group(1).strip() if label_match else name

                # Extract options for radio/checkbox/select
                options = []
                if qtype in (QuestionType.RADIO, QuestionType.CHECKBOX):
                    option_pattern = rf'<input[^>]*name=["\']?{re.escape(name)}["\']?[^>]*value=["\']([^"\']+)["\']'
                    for opt_match in re.finditer(option_pattern, html):
                        value = opt_match.group(1)
                        options.append(QuestionOption(value=value, label=value))

                elif qtype == QuestionType.DROPDOWN:
                    # Find the select element and its options
                    select_match = re.search(
                        rf'<select[^>]*name=["\']?{re.escape(name)}["\']?[^>]*>(.*?)</select>',
                        html,
                        re.DOTALL | re.IGNORECASE,
                    )
                    if select_match:
                        select_html = select_match.group(1)
                        for opt_match in re.finditer(
                            r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)<', select_html
                        ):
                            options.append(
                                QuestionOption(
                                    value=opt_match.group(1), label=opt_match.group(2).strip()
                                )
                            )

                questions.append(
                    Question(
                        id=name,
                        type=qtype,
                        text=text,
                        options=options,
                        element_selector=f'[name="{name}"]',
                    )
                )

        return questions

    def _detect_question_type(self, html: str, qid: str) -> QuestionType:
        """Detect question type from HTML context."""
        for qtype, patterns in self.QUESTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return qtype

        return QuestionType.UNKNOWN

    def _extract_options(self, html: str, qid: str, qtype: QuestionType) -> list[QuestionOption]:
        """Extract answer options for a question."""
        options = []

        if qtype == QuestionType.RADIO or qtype == QuestionType.CHECKBOX:
            # Find input elements with labels
            pattern = r'<input[^>]*value=["\']([^"\']+)["\'][^>]*>.*?<label[^>]*>([^<]+)<'
            for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
                options.append(
                    QuestionOption(
                        value=match.group(1),
                        label=match.group(2).strip(),
                    )
                )

        elif qtype == QuestionType.DROPDOWN:
            pattern = r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)<'
            for match in re.finditer(pattern, html):
                if match.group(1):  # Skip empty values
                    options.append(
                        QuestionOption(
                            value=match.group(1),
                            label=match.group(2).strip(),
                        )
                    )

        return options

    def _extract_navigation(self, html: str, platform: str) -> dict[str, Any]:
        """Extract navigation elements (next/submit buttons)."""
        result = {
            "has_next": False,
            "next_selector": None,
            "submit_selector": None,
            "total_pages": 1,
        }

        # Next button patterns
        next_patterns = [
            (r'id=["\']NextButton["\']', "#NextButton"),
            (r'class="[^"]*next-button[^"]*"', ".next-button"),
            (r'value=["\']Next["\']', '[value="Next"]'),
            (r'data-action=["\']next["\']', '[data-action="next"]'),
            (r">Next<", 'button:contains("Next")'),
            (r">Continue<", 'button:contains("Continue")'),
        ]

        for pattern, selector in next_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                result["has_next"] = True
                result["next_selector"] = selector
                break

        # Submit button patterns
        submit_patterns = [
            (r'type=["\']submit["\']', '[type="submit"]'),
            (r'id=["\']SubmitButton["\']', "#SubmitButton"),
            (r">Submit<", 'button:contains("Submit")'),
            (r">Finish<", 'button:contains("Finish")'),
            (r">Done<", 'button:contains("Done")'),
        ]

        for pattern, selector in submit_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                result["submit_selector"] = selector
                break

        # Try to detect total pages
        page_pattern = r"Page\s+(\d+)\s+of\s+(\d+)"
        page_match = re.search(page_pattern, html)
        if page_match:
            result["total_pages"] = int(page_match.group(2))

        return result
