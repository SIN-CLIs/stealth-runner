"""
Intelligent Answer Engine - Generates consistent, believable survey responses.

Features:
    - Persona-based answer generation
    - Consistency checking across questions
    - Anti-pattern detection (avoid bot behavior)
    - Attention check handling
    - LLM integration for open-text questions
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .survey_parser import Question, QuestionType, QuestionOption

logger = logging.getLogger(__name__)


@dataclass
class Persona:
    """Survey respondent persona for consistent answers."""
    # Demographics
    age: int = 32
    gender: str = "male"
    income_bracket: str = "50k-75k"
    education: str = "bachelors"
    occupation: str = "software_developer"
    location: str = "US"
    marital_status: str = "single"
    children: int = 0

    # Preferences
    interests: list[str] = field(default_factory=lambda: ["technology", "gaming"])
    brands: dict[str, str] = field(default_factory=dict)  # category -> preferred brand
    political_leaning: str = "moderate"

    # Behavior patterns
    shopping_frequency: str = "weekly"
    social_media_usage: str = "daily"
    news_sources: list[str] = field(default_factory=lambda: ["online"])

    def to_dict(self) -> dict:
        """Convert persona to dictionary."""
        return {
            "age": self.age,
            "gender": self.gender,
            "income_bracket": self.income_bracket,
            "education": self.education,
            "occupation": self.occupation,
            "location": self.location,
            "marital_status": self.marital_status,
            "children": self.children,
            "interests": self.interests,
            "brands": self.brands,
            "political_leaning": self.political_leaning,
            "shopping_frequency": self.shopping_frequency,
            "social_media_usage": self.social_media_usage,
            "news_sources": self.news_sources,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Persona":
        """Create persona from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Answer:
    """Generated answer for a survey question."""
    question_id: str
    question_hash: str  # For consistency tracking
    value: Any
    confidence: float = 1.0
    reasoning: str = ""


class AnswerEngine:
    """
    Intelligent answer generation engine.

    Generates consistent, believable answers based on persona
    and maintains history for cross-survey consistency.
    """

    # Attention check patterns
    ATTENTION_CHECK_PATTERNS = [
        r"please select (option |the |)(\w+)",
        r"choose (option |the |)(\w+)",
        r"select (the |)(\w+) answer",
        r"to show you.re paying attention",
        r"quality control",
        r"attention check",
        r"please select .*(strongly agree|disagree|neutral)",
    ]

    # Income bracket mappings
    INCOME_BRACKETS = {
        "under_25k": (0, 25000),
        "25k-50k": (25000, 50000),
        "50k-75k": (50000, 75000),
        "75k-100k": (75000, 100000),
        "100k-150k": (100000, 150000),
        "over_150k": (150000, 500000),
    }

    # Age group mappings
    AGE_GROUPS = {
        "18-24": (18, 24),
        "25-34": (25, 34),
        "35-44": (35, 44),
        "45-54": (45, 54),
        "55-64": (55, 64),
        "65+": (65, 100),
    }

    def __init__(
        self,
        persona: Persona,
        db_path: str | Path = "~/.survey_agent/answers.db",
        llm_provider: str | None = None,
        llm_api_key: str | None = None,
    ):
        self.persona = persona
        self.db_path = Path(db_path).expanduser()
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key

        self._current_session_answers: dict[str, Answer] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize answer history database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS answer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_hash TEXT NOT NULL,
                question_text TEXT,
                answer_value TEXT,
                persona_hash TEXT,
                created_at TEXT,
                UNIQUE(question_hash, persona_hash)
            )
        """)
        conn.commit()
        conn.close()

    def _hash_question(self, question: Question) -> str:
        """Generate consistent hash for a question."""
        # Normalize question text for hashing
        normalized = re.sub(r'\s+', ' ', question.text.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _hash_persona(self) -> str:
        """Generate hash for current persona."""
        persona_str = json.dumps(self.persona.to_dict(), sort_keys=True)
        return hashlib.sha256(persona_str.encode()).hexdigest()[:16]

    def generate_answer(self, question: Question) -> Answer:
        """
        Generate an answer for a survey question.

        Args:
            question: Parsed survey question

        Returns:
            Generated answer with confidence score
        """
        question_hash = self._hash_question(question)

        # Check for attention check
        if self._is_attention_check(question):
            return self._handle_attention_check(question, question_hash)

        # Check history for consistency
        historical = self._get_historical_answer(question_hash)
        if historical:
            logger.info(f"Using historical answer for question: {question.text[:50]}")
            return Answer(
                question_id=question.id,
                question_hash=question_hash,
                value=historical,
                confidence=1.0,
                reasoning="Historical consistency",
            )

        # Generate new answer based on question type
        answer = self._generate_by_type(question, question_hash)

        # Store in session
        self._current_session_answers[question.id] = answer

        # Store in history
        self._store_answer(question, answer)

        return answer

    def _generate_by_type(self, question: Question, question_hash: str) -> Answer:
        """Generate answer based on question type."""
        generators = {
            QuestionType.RADIO: self._generate_radio_answer,
            QuestionType.CHECKBOX: self._generate_checkbox_answer,
            QuestionType.SLIDER: self._generate_slider_answer,
            QuestionType.DROPDOWN: self._generate_dropdown_answer,
            QuestionType.OPEN_TEXT: self._generate_open_text_answer,
            QuestionType.MATRIX: self._generate_matrix_answer,
            QuestionType.NUMBER: self._generate_number_answer,
            QuestionType.DATE: self._generate_date_answer,
            QuestionType.LIKERT: self._generate_likert_answer,
            QuestionType.NPS: self._generate_nps_answer,
            QuestionType.RANKING: self._generate_ranking_answer,
        }

        generator = generators.get(question.type, self._generate_default_answer)
        return generator(question, question_hash)

    def _generate_radio_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate radio button answer."""
        if not question.options:
            return self._generate_default_answer(question, question_hash)

        # Check for demographic questions
        text_lower = question.text.lower()

        # Age question
        if any(kw in text_lower for kw in ["age", "how old", "birth year"]):
            return self._select_age_option(question, question_hash)

        # Gender question
        if any(kw in text_lower for kw in ["gender", "sex", "male/female"]):
            return self._select_gender_option(question, question_hash)

        # Income question
        if any(kw in text_lower for kw in ["income", "salary", "earnings", "household income"]):
            return self._select_income_option(question, question_hash)

        # Education question
        if any(kw in text_lower for kw in ["education", "degree", "school"]):
            return self._select_education_option(question, question_hash)

        # Default: weighted random with preference for middle options
        weights = self._calculate_option_weights(question.options)
        selected = random.choices(question.options, weights=weights, k=1)[0]

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=selected.value,
            confidence=0.8,
            reasoning="Weighted random selection",
        )

    def _generate_checkbox_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate checkbox (multi-select) answer."""
        if not question.options:
            return self._generate_default_answer(question, question_hash)

        # Select 1-3 options based on persona interests
        num_selections = random.randint(1, min(3, len(question.options)))

        # Prefer options matching persona interests
        scored_options = []
        for opt in question.options:
            score = 1.0
            opt_lower = opt.label.lower()
            for interest in self.persona.interests:
                if interest.lower() in opt_lower:
                    score += 2.0
            scored_options.append((opt, score))

        # Sort by score and select top N
        scored_options.sort(key=lambda x: x[1], reverse=True)
        selected = [opt.value for opt, _ in scored_options[:num_selections]]

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=selected,
            confidence=0.7,
            reasoning="Interest-based selection",
        )

    def _generate_slider_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate slider/range answer."""
        min_val = question.min_value or 0
        max_val = question.max_value or 100

        # Tend toward moderate values (normal distribution around center)
        center = (min_val + max_val) / 2
        std_dev = (max_val - min_val) / 6  # 99.7% within range

        value = int(random.gauss(center, std_dev))
        value = max(min_val, min(max_val, value))  # Clamp to range

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=value,
            confidence=0.8,
            reasoning="Normal distribution around center",
        )

    def _generate_dropdown_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate dropdown answer (similar to radio)."""
        return self._generate_radio_answer(question, question_hash)

    def _generate_open_text_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate open text answer."""
        # If LLM available, use it
        if self.llm_provider and self.llm_api_key:
            return self._generate_llm_answer(question, question_hash)

        # Fallback: template-based responses
        text_lower = question.text.lower()

        templates = {
            "why": [
                "I find it useful for my daily needs.",
                "It matches my lifestyle and preferences.",
                "Based on my experience, it works well for me.",
            ],
            "how": [
                "I typically do this on a regular basis.",
                "It fits naturally into my routine.",
                "I approach it methodically.",
            ],
            "what": [
                "It depends on the specific situation.",
                "Several factors influence my choice.",
                "I consider multiple aspects before deciding.",
            ],
            "describe": [
                "In my experience, it has been positive overall.",
                "I would characterize it as satisfactory.",
                "It meets my expectations for the most part.",
            ],
        }

        # Select template based on question keywords
        response = "I don't have a specific answer for this question."
        for keyword, responses in templates.items():
            if keyword in text_lower:
                response = random.choice(responses)
                break

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=response,
            confidence=0.6,
            reasoning="Template-based response",
        )

    def _generate_llm_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate answer using LLM."""
        # TODO: Implement actual LLM call
        prompt = f"""You are a survey respondent with the following profile:
- Age: {self.persona.age}
- Gender: {self.persona.gender}
- Occupation: {self.persona.occupation}
- Interests: {', '.join(self.persona.interests)}

Answer this survey question naturally and concisely (1-2 sentences):
{question.text}

Your response:"""

        # Placeholder - would call actual LLM API
        logger.info(f"LLM prompt: {prompt[:100]}...")

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value="Based on my experience, I find this to be generally positive.",
            confidence=0.7,
            reasoning="LLM-generated response",
        )

    def _generate_matrix_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate matrix/grid answer."""
        answers = {}

        for row in question.rows:
            # Generate a response for each row
            if question.columns:
                # Tend toward middle columns
                mid = len(question.columns) // 2
                selected_idx = int(random.gauss(mid, 1))
                selected_idx = max(0, min(len(question.columns) - 1, selected_idx))
                answers[row] = question.columns[selected_idx]
            else:
                answers[row] = random.randint(1, 5)

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=answers,
            confidence=0.7,
            reasoning="Matrix response with center tendency",
        )

    def _generate_number_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate number input answer."""
        # Try to infer reasonable range from question text
        text_lower = question.text.lower()

        if "how many" in text_lower:
            value = random.randint(1, 10)
        elif "hours" in text_lower:
            value = random.randint(1, 8)
        elif "times" in text_lower:
            value = random.randint(1, 5)
        else:
            value = random.randint(1, 100)

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=value,
            confidence=0.7,
            reasoning="Contextual number generation",
        )

    def _generate_date_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate date answer."""
        # Default to recent date
        from datetime import timedelta

        days_ago = random.randint(1, 30)
        date = datetime.now() - timedelta(days=days_ago)

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=date.strftime("%Y-%m-%d"),
            confidence=0.8,
            reasoning="Recent date selection",
        )

    def _generate_likert_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate Likert scale answer (strongly disagree to strongly agree)."""
        # Tend toward agree/neutral
        options = [1, 2, 3, 4, 5]
        weights = [0.1, 0.15, 0.25, 0.3, 0.2]
        value = random.choices(options, weights=weights, k=1)[0]

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=value,
            confidence=0.8,
            reasoning="Likert with positive tendency",
        )

    def _generate_nps_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate NPS (0-10) answer."""
        # Tend toward 7-8 (passive)
        value = int(random.gauss(7.5, 1.5))
        value = max(0, min(10, value))

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=value,
            confidence=0.8,
            reasoning="NPS with passive tendency",
        )

    def _generate_ranking_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate ranking answer."""
        if not question.options:
            return self._generate_default_answer(question, question_hash)

        # Random shuffle with some preference for interest-related items at top
        options = list(question.options)
        random.shuffle(options)

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value=[opt.value for opt in options],
            confidence=0.7,
            reasoning="Randomized ranking",
        )

    def _generate_default_answer(self, question: Question, question_hash: str) -> Answer:
        """Generate default answer when type is unknown."""
        if question.options:
            selected = random.choice(question.options)
            return Answer(
                question_id=question.id,
                question_hash=question_hash,
                value=selected.value,
                confidence=0.5,
                reasoning="Random selection (unknown type)",
            )

        return Answer(
            question_id=question.id,
            question_hash=question_hash,
            value="N/A",
            confidence=0.3,
            reasoning="Default fallback",
        )

    def _is_attention_check(self, question: Question) -> bool:
        """Detect if question is an attention check."""
        text_lower = question.text.lower()

        for pattern in self.ATTENTION_CHECK_PATTERNS:
            if re.search(pattern, text_lower):
                logger.info(f"Attention check detected: {question.text[:50]}")
                return True

        return False

    def _handle_attention_check(self, question: Question, question_hash: str) -> Answer:
        """Handle attention check question."""
        text_lower = question.text.lower()

        # Try to find the required answer
        for pattern in self.ATTENTION_CHECK_PATTERNS:
            match = re.search(pattern, text_lower)
            if match and len(match.groups()) >= 2:
                required = match.group(2).lower()

                # Find matching option
                for opt in question.options:
                    if required in opt.label.lower() or required in opt.value.lower():
                        return Answer(
                            question_id=question.id,
                            question_hash=question_hash,
                            value=opt.value,
                            confidence=1.0,
                            reasoning="Attention check - direct match",
                        )

        # Fallback: look for exact option match in question text
        for opt in question.options:
            if opt.label.lower() in text_lower:
                return Answer(
                    question_id=question.id,
                    question_hash=question_hash,
                    value=opt.value,
                    confidence=0.9,
                    reasoning="Attention check - option in text",
                )

        # Last resort: random
        return self._generate_radio_answer(question, question_hash)

    def _select_age_option(self, question: Question, question_hash: str) -> Answer:
        """Select age-appropriate option."""
        for opt in question.options:
            for bracket, (min_age, max_age) in self.AGE_GROUPS.items():
                if bracket in opt.label or bracket in opt.value:
                    if min_age <= self.persona.age <= max_age:
                        return Answer(
                            question_id=question.id,
                            question_hash=question_hash,
                            value=opt.value,
                            confidence=1.0,
                            reasoning="Age bracket match",
                        )

        # Fallback to closest match
        return self._generate_radio_answer(question, question_hash)

    def _select_gender_option(self, question: Question, question_hash: str) -> Answer:
        """Select gender option."""
        for opt in question.options:
            if self.persona.gender.lower() in opt.label.lower():
                return Answer(
                    question_id=question.id,
                    question_hash=question_hash,
                    value=opt.value,
                    confidence=1.0,
                    reasoning="Gender match",
                )

        return self._generate_radio_answer(question, question_hash)

    def _select_income_option(self, question: Question, question_hash: str) -> Answer:
        """Select income-appropriate option."""
        persona_range = self.INCOME_BRACKETS.get(
            self.persona.income_bracket, (50000, 75000)
        )
        persona_mid = (persona_range[0] + persona_range[1]) / 2

        best_match = None
        best_distance = float('inf')

        for opt in question.options:
            # Try to extract numbers from option
            numbers = re.findall(r'[\d,]+', opt.label.replace(',', ''))
            if numbers:
                opt_mid = sum(int(n) for n in numbers) / len(numbers)
                distance = abs(opt_mid - persona_mid)
                if distance < best_distance:
                    best_distance = distance
                    best_match = opt

        if best_match:
            return Answer(
                question_id=question.id,
                question_hash=question_hash,
                value=best_match.value,
                confidence=0.9,
                reasoning="Income bracket match",
            )

        return self._generate_radio_answer(question, question_hash)

    def _select_education_option(self, question: Question, question_hash: str) -> Answer:
        """Select education-appropriate option."""
        education_keywords = {
            "high_school": ["high school", "secondary", "ged"],
            "some_college": ["some college", "associate"],
            "bachelors": ["bachelor", "undergraduate", "college degree", "4-year"],
            "masters": ["master", "graduate", "mba"],
            "doctorate": ["phd", "doctorate", "doctoral"],
        }

        target_keywords = education_keywords.get(self.persona.education, [])

        for opt in question.options:
            opt_lower = opt.label.lower()
            for keyword in target_keywords:
                if keyword in opt_lower:
                    return Answer(
                        question_id=question.id,
                        question_hash=question_hash,
                        value=opt.value,
                        confidence=1.0,
                        reasoning="Education match",
                    )

        return self._generate_radio_answer(question, question_hash)

    def _calculate_option_weights(self, options: list[QuestionOption]) -> list[float]:
        """Calculate selection weights (prefer middle options)."""
        n = len(options)
        if n <= 1:
            return [1.0]

        # Bell curve weights centered on middle
        weights = []
        center = (n - 1) / 2
        for i in range(n):
            distance = abs(i - center)
            weight = 1.0 / (1.0 + distance)
            weights.append(weight)

        # Normalize
        total = sum(weights)
        return [w / total for w in weights]

    def _get_historical_answer(self, question_hash: str) -> Any | None:
        """Get historical answer for consistency."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT answer_value FROM answer_history WHERE question_hash = ? AND persona_hash = ?",
            (question_hash, self._hash_persona())
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return row[0]

        return None

    def _store_answer(self, question: Question, answer: Answer) -> None:
        """Store answer in history database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO answer_history
            (question_hash, question_text, answer_value, persona_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            answer.question_hash,
            question.text[:500],
            json.dumps(answer.value),
            self._hash_persona(),
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
        conn.close()

    def validate_consistency(self, answers: list[Answer]) -> list[str]:
        """
        Validate answer consistency within a survey.

        Returns list of inconsistency warnings.
        """
        warnings = []

        # Check for contradictions
        # TODO: Implement more sophisticated consistency checks

        return warnings
