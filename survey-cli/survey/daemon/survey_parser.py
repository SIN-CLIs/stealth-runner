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
    - Drag-and-drop (SR-150)
    - Hotspot / image-click (SR-150)
    - Conjoint choice (SR-150)
    - MaxDiff best/worst (SR-150)
    - Video ad attention (SR-150)
    - Audio ad attention (SR-150)
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
    """Supported survey question types.
    
    SR-150 extended: AUDIO_AD, CONJOINT, DRAG_DROP, HOTSPOT, MAX_DIFF, VIDEO_AD.
    """
    AUDIO_AD = "audio_ad"          # SR-150: must-listen ad attention
    CHECKBOX = "checkbox"
    CONJOINT = "conjoint"          # SR-150: Sawtooth-style profile choice
    DATE = "date"
    DRAG_DROP = "drag_drop"        # SR-150: drag-to-rank / drag-to-bucket
    DROPDOWN = "dropdown"
    FILE_UPLOAD = "file_upload"
    HOTSPOT = "hotspot"            # SR-150: click image regions
    LIKERT = "likert"
    MATRIX = "matrix"
    MAX_DIFF = "max_diff"          # SR-150: best/worst scaling
    NPS = "nps"
    NUMBER = "number"
    OPEN_TEXT = "open_text"
    RADIO = "radio"
    RANKING = "ranking"
    SLIDER = "slider"
    UNKNOWN = "unknown"
    VIDEO_AD = "video_ad"          # SR-150: must-watch ad attention


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
    # SR-150: additional fields for extended types
    media_selector: str | None = None  # For VIDEO_AD / AUDIO_AD
    hotspot_areas: list[dict[str, Any]] = field(default_factory=list)  # For HOTSPOT
    conjoint_cards: list[dict[str, Any]] = field(default_factory=list)  # For CONJOINT


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

    # Question type detection patterns — order matters: more specific types first (SR-150)
    QUESTION_PATTERNS = {
        # SR-150: new extended types (detect before generic fallback)
        QuestionType.DRAG_DROP: [
            r'\[draggable=["\']true["\']\]',
            r'class="[^"]*ui-sortable[^"]*"',
            r'class="[^"]*react-beautiful-dnd[^"]*"',
            r'data-rbd-draggable-id',
            r'class="[^"]*sortable-handle[^"]*"',
            r'class="[^"]*draggable-item[^"]*"',
        ],
        QuestionType.HOTSPOT: [
            r'<map[^>]*name=',
            r'\[data-hotspot\]',
            r'class="[^"]*clickable-image[^"]*"',
            r'class="[^"]*hotspot-container[^"]*"',
            r'QID\d+[^>]*hotspot',
        ],
        QuestionType.CONJOINT: [
            r'\[data-conjoint-task\]',
            r'<form[^>]*name=["\']ConjointForm["\']',
            r'class="[^"]*conjoint-card[^"]*"',
            r'class="[^"]*profile-card[^"]*".*Choose this',
            r'sawtooth.*conjoint',
        ],
        QuestionType.MAX_DIFF: [
            r'\[data-maxdiff\]',
            r'class="[^"]*maxdiff[^"]*"',
            r'(Most|Least|Am meisten|Am wenigsten).*radio',
            r'best.?worst.*scaling',
        ],
        QuestionType.VIDEO_AD: [
            r'<video[^>]*>.*Continue.*disabled',
            r'data-min-watch-seconds',
            r'class="[^"]*video-ad[^"]*"',
            r'<video[^>]*autoplay[^>]*>',
        ],
        QuestionType.AUDIO_AD: [
            r'<audio[^>]*>.*Continue.*disabled',
            r'class="[^"]*audio-ad[^"]*"',
            r'<audio[^>]*autoplay[^>]*>',
        ],
        # Original types
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
                    site_key_match = re.search(
                        r'data-sitekey=["\']([^"\']+)["\']',
                        html
                    )
                    if site_key_match:
                        result["site_key"] = site_key_match.group(1)

                    logger.info(f"Captcha detected: {captcha_type}")
                    return result

        return result

    async def _extract_questions(
        self, html: str, platform: str
    ) -> list[Question]:
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

            q = Question(
                id=qid,
                type=qtype,
                text=text,
                options=options,
                element_selector=f"#{qid}",
            )
            # SR-150: extract extended type metadata
            self._extract_extended_type_metadata(q, html, qid)
            questions.append(q)

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
            text_match = re.search(
                r'class="question-title[^"]*"[^>]*>([^<]+)<',
                context
            )
            text = text_match.group(1).strip() if text_match else ""

            qtype = self._detect_question_type(context, qid)
            options = self._extract_options(context, qid, qtype)

            q = Question(
                id=qid,
                type=qtype,
                text=text,
                options=options,
            )
            self._extract_extended_type_metadata(q, context, qid)
            questions.append(q)

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
                context = html[start:match.end()]

                text_match = re.search(
                    r'class="[^"]*freebirdFormviewerComponentsQuestionBaseTitle[^"]*"[^>]*>([^<]+)<',
                    context
                )
                text = text_match.group(1).strip() if text_match else f"Question {i+1}"

                qtype = self._detect_question_type(context, qid)
                options = self._extract_options(context, qid, qtype)

                q = Question(
                    id=qid,
                    type=qtype,
                    text=text,
                    options=options,
                )
                self._extract_extended_type_metadata(q, context, qid)
                questions.append(q)
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
            (r'<select[^>]*>.*?</select>', QuestionType.DROPDOWN),
            (r'<textarea[^>]*>', QuestionType.OPEN_TEXT),
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
                    re.IGNORECASE
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
                        re.DOTALL | re.IGNORECASE
                    )
                    if select_match:
                        select_html = select_match.group(1)
                        for opt_match in re.finditer(
                            r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)<',
                            select_html
                        ):
                            options.append(QuestionOption(
                                value=opt_match.group(1),
                                label=opt_match.group(2).strip()
                            ))

                q = Question(
                    id=name,
                    type=qtype,
                    text=text,
                    options=options,
                    element_selector=f'[name="{name}"]',
                )
                self._extract_extended_type_metadata(q, html, name)
                questions.append(q)

        # SR-150: also detect standalone extended types (video/audio ads, drag-drop, etc.)
        self._extract_standalone_extended_questions(html, questions, seen_names)

        return questions

    def _extract_standalone_extended_questions(
        self, html: str, questions: list[Question], seen_names: set[str]
    ) -> None:
        """SR-150: Extract extended question types that may not follow standard form patterns."""
        # Video ads
        for i, match in enumerate(re.finditer(r'<video[^>]*id=["\']([^"\']+)["\'][^>]*>', html)):
            vid_id = match.group(1)
            if vid_id in seen_names:
                continue
            seen_names.add(vid_id)
            q = Question(
                id=vid_id,
                type=QuestionType.VIDEO_AD,
                text="Video Ad",
                media_selector=f"#{vid_id}",
            )
            questions.append(q)

        # Audio ads
        for i, match in enumerate(re.finditer(r'<audio[^>]*id=["\']([^"\']+)["\'][^>]*>', html)):
            aud_id = match.group(1)
            if aud_id in seen_names:
                continue
            seen_names.add(aud_id)
            q = Question(
                id=aud_id,
                type=QuestionType.AUDIO_AD,
                text="Audio Ad",
                media_selector=f"#{aud_id}",
            )
            questions.append(q)

        # Drag-drop containers
        for i, match in enumerate(re.finditer(r'data-rbd-draggable-id=["\']([^"\']+)["\']', html)):
            drag_id = f"drag_{match.group(1)}"
            if drag_id in seen_names:
                continue
            seen_names.add(drag_id)
            q = Question(
                id=drag_id,
                type=QuestionType.DRAG_DROP,
                text="Drag and Drop",
            )
            questions.append(q)

    def _detect_question_type(self, html: str, qid: str) -> QuestionType:
        """Detect question type from HTML context.
        
        SR-150: extended types checked first (drag-drop, hotspot, conjoint, max-diff, video-ad, audio-ad).
        """
        for qtype, patterns in self.QUESTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE | re.DOTALL):
                    return qtype

        return QuestionType.UNKNOWN

    def _extract_extended_type_metadata(
        self, question: Question, html: str, qid: str
    ) -> None:
        """SR-150: Extract additional metadata for extended question types."""
        if question.type == QuestionType.VIDEO_AD:
            # Extract video selector
            video_match = re.search(r'<video[^>]*id=["\']([^"\']+)["\']', html)
            if video_match:
                question.media_selector = f"#{video_match.group(1)}"
            else:
                question.media_selector = "video"

        elif question.type == QuestionType.AUDIO_AD:
            audio_match = re.search(r'<audio[^>]*id=["\']([^"\']+)["\']', html)
            if audio_match:
                question.media_selector = f"#{audio_match.group(1)}"
            else:
                question.media_selector = "audio"

        elif question.type == QuestionType.HOTSPOT:
            # Extract image map areas
            map_match = re.search(r'<map[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</map>', html, re.DOTALL)
            if map_match:
                areas = []
                for area_match in re.finditer(
                    r'<area[^>]*coords=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?',
                    map_match.group(2)
                ):
                    coords = [int(c) for c in area_match.group(1).split(",")]
                    areas.append({
                        "coords": coords,
                        "label": area_match.group(2) or "",
                    })
                question.hotspot_areas = areas

        elif question.type == QuestionType.CONJOINT:
            # Extract conjoint profile cards
            cards = []
            for card_match in re.finditer(
                r'class="[^"]*(?:conjoint-card|profile-card)[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL
            ):
                card_html = card_match.group(1)
                features = {}
                # Extract feature rows
                for feat_match in re.finditer(
                    r'class="[^"]*feature[^"]*"[^>]*>([^<]+)</.*?class="[^"]*value[^"]*"[^>]*>([^<]+)<',
                    card_html, re.DOTALL
                ):
                    features[feat_match.group(1).strip()] = feat_match.group(2).strip()
                if features:
                    cards.append({"features": features})
            question.conjoint_cards = cards

    def _extract_options(
        self, html: str, qid: str, qtype: QuestionType
    ) -> list[QuestionOption]:
        """Extract answer options for a question."""
        options = []

        if qtype == QuestionType.RADIO or qtype == QuestionType.CHECKBOX:
            # Find input elements with labels
            pattern = r'<input[^>]*value=["\']([^"\']+)["\'][^>]*>.*?<label[^>]*>([^<]+)<'
            for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
                options.append(QuestionOption(
                    value=match.group(1),
                    label=match.group(2).strip(),
                ))

        elif qtype == QuestionType.DROPDOWN:
            pattern = r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)<'
            for match in re.finditer(pattern, html):
                if match.group(1):  # Skip empty values
                    options.append(QuestionOption(
                        value=match.group(1),
                        label=match.group(2).strip(),
                    ))

        elif qtype == QuestionType.MAX_DIFF:
            # SR-150: extract items for best/worst selection
            for match in re.finditer(
                r'class="[^"]*maxdiff-item[^"]*"[^>]*>([^<]+)<',
                html
            ):
                options.append(QuestionOption(
                    value=match.group(1).strip(),
                    label=match.group(1).strip(),
                ))

        elif qtype == QuestionType.DRAG_DROP:
            # SR-150: extract draggable items
            for match in re.finditer(
                r'data-rbd-draggable-id=["\']([^"\']+)["\'][^>]*>([^<]*)<',
                html
            ):
                options.append(QuestionOption(
                    value=match.group(1),
                    label=match.group(2).strip() or match.group(1),
                ))

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
            (r'>Next<', 'button:contains("Next")'),
            (r'>Continue<', 'button:contains("Continue")'),
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
            (r'>Submit<', 'button:contains("Submit")'),
            (r'>Finish<', 'button:contains("Finish")'),
            (r'>Done<', 'button:contains("Done")'),
        ]

        for pattern, selector in submit_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                result["submit_selector"] = selector
                break

        # Try to detect total pages
        page_pattern = r'Page\s+(\d+)\s+of\s+(\d+)'
        page_match = re.search(page_pattern, html)
        if page_match:
            result["total_pages"] = int(page_match.group(2))

        return result
