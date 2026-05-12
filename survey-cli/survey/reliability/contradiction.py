"""
Persona Contradiction Detector — Scans answer history for cross-panel inconsistencies.

SR-152: Prevents fraud flags from inconsistent demographic answers.

Categories:
    - AGE: age, alter, born, wie alt
    - GENDER: gender, geschlecht, sex
    - INCOME: income, einkommen, salary, household income
    - EDUCATION: education, bildung, degree, abschluss
    - EMPLOYMENT: employment, beruf, occupation
    - HOUSEHOLD_SIZE: how many people, haushaltsgroesse
    - COUNTRY: country, land, region
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ANSWER_DB = Path("~/.survey_agent/answers.db").expanduser()


class IdentityCategory:
    """Identity question categories with EN + DE keywords."""
    
    AGE = "AGE"
    GENDER = "GENDER"
    INCOME = "INCOME"
    EDUCATION = "EDUCATION"
    EMPLOYMENT = "EMPLOYMENT"
    HOUSEHOLD_SIZE = "HOUSEHOLD_SIZE"
    COUNTRY = "COUNTRY"
    
    # Keywords for each category (EN + DE)
    PATTERNS = {
        AGE: [
            r"\bage\b", r"\balter\b", r"\bborn\b", r"\bwie alt\b",
            r"\bbirth\s*year\b", r"\bgeburtsjahr\b", r"\byear.*born\b",
            r"\bhow old\b", r"\byears old\b", r"\bjahre alt\b",
        ],
        GENDER: [
            r"\bgender\b", r"\bgeschlecht\b", r"\bsex\b",
            r"\bmale\b", r"\bfemale\b", r"\bmaennlich\b", r"\bweiblich\b",
            r"\bmann\b", r"\bfrau\b", r"\bdivers\b",
        ],
        INCOME: [
            r"\bincome\b", r"\beinkommen\b", r"\bsalary\b", r"\bgehalt\b",
            r"\bhousehold income\b", r"\bhaushaltseinkommen\b",
            r"\bearnings\b", r"\bverdienst\b", r"\bannual income\b",
        ],
        EDUCATION: [
            r"\beducation\b", r"\bbildung\b", r"\bdegree\b", r"\babschluss\b",
            r"\bhighest.*degree\b", r"\bhoechster.*abschluss\b",
            r"\bschool\b", r"\bschule\b", r"\buniversity\b", r"\bhochschule\b",
        ],
        EMPLOYMENT: [
            r"\bemployment\b", r"\bberuf\b", r"\boccupation\b", r"\bjob\b",
            r"\bwork\b", r"\barbeit\b", r"\bemployed\b", r"\bbeschaeftigt\b",
            r"\bposition\b", r"\bstelle\b", r"\bcareer\b",
        ],
        HOUSEHOLD_SIZE: [
            r"\bhousehold.*size\b", r"\bhaushaltsgroesse\b",
            r"\bhow many.*people\b", r"\bwie viele.*personen\b",
            r"\bfamily.*size\b", r"\bpeople.*household\b",
            r"\bmembers.*household\b", r"\bhaushaltsmitglieder\b",
        ],
        COUNTRY: [
            r"\bcountry\b", r"\bland\b", r"\bregion\b",
            r"\bstate\b", r"\bbundesland\b", r"\blocation\b",
            r"\bwhere.*live\b", r"\bwo.*wohnen\b", r"\bresidence\b",
        ],
    }


@dataclass
class Contradiction:
    """A detected contradiction in answer history."""
    category: str
    persona_id: str
    answers: dict[str, int]  # answer_value -> count
    most_frequent: str
    most_frequent_count: int
    total_count: int
    is_contradicted: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "persona_id": self.persona_id,
            "answers": self.answers,
            "most_frequent": self.most_frequent,
            "most_frequent_count": self.most_frequent_count,
            "total_count": self.total_count,
            "is_contradicted": self.is_contradicted,
        }


@dataclass
class PinnedAnswer:
    """A pinned answer from contradiction detection."""
    category: str
    value: str
    confidence: float
    reasoning: str


class ContradictionDetector:
    """
    Detects and resolves persona identity contradictions.
    
    Usage:
        detector = ContradictionDetector()
        pinned = detector.check(persona_id, question)
        if pinned:
            return pinned  # Use this answer instead of generating new
        
        report = detector.scan(persona_id)
    """
    
    def __init__(self, db_path: Path | str = DEFAULT_ANSWER_DB):
        """
        Initialize contradiction detector.
        
        Args:
            db_path: Path to answer history SQLite database
        """
        self.db_path = Path(db_path).expanduser()
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Ensure the answer_history table has required columns."""
        if not self.db_path.exists():
            return
        
        conn = sqlite3.connect(self.db_path)
        try:
            # Check if identity_category column exists
            cursor = conn.execute("PRAGMA table_info(answer_history)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if "identity_category" not in columns:
                conn.execute(
                    "ALTER TABLE answer_history ADD COLUMN identity_category TEXT"
                )
                conn.commit()
                logger.info("Added identity_category column to answer_history")
        except sqlite3.OperationalError:
            pass  # Table doesn't exist yet
        finally:
            conn.close()
    
    def categorize(self, question_text: str) -> str | None:
        """
        Categorize a question into an identity category.
        
        Args:
            question_text: The question text
            
        Returns:
            Category name (AGE, GENDER, etc.) or None if not an identity question
        """
        text_lower = question_text.lower()
        
        for category, patterns in IdentityCategory.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return category
        
        return None
    
    def _get_prior_answers(
        self,
        persona_id: str,
        category: str,
    ) -> dict[str, int]:
        """
        Get prior answers for a persona+category combination.
        
        Args:
            persona_id: Persona identifier
            category: Identity category
            
        Returns:
            Dictionary of answer_value -> count
        """
        if not self.db_path.exists():
            return {}
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT answer_value, COUNT(*) as cnt
                FROM answer_history
                WHERE persona_hash = ? AND identity_category = ?
                GROUP BY answer_value
                ORDER BY cnt DESC
            """, (persona_id, category))
            
            return {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()
    
    def _find_closest_option(
        self,
        prior_answer: str,
        options: list[Any],
    ) -> Any | None:
        """
        Find the option closest to the prior answer.
        
        Handles cases like prior="25-34" and options=["26-35", "36-45", ...]
        
        Args:
            prior_answer: The prior answer value
            options: Available options
            
        Returns:
            Closest matching option or None
        """
        if not options:
            return None
        
        prior_lower = prior_answer.lower().strip()
        
        # Extract numeric ranges from prior answer
        prior_nums = [int(x) for x in re.findall(r'\d+', prior_answer)]
        prior_mid = sum(prior_nums) / len(prior_nums) if prior_nums else None
        
        best_option = None
        best_score = -1
        
        for opt in options:
            opt_value = opt.value if hasattr(opt, 'value') else str(opt)
            opt_label = opt.label if hasattr(opt, 'label') else str(opt)
            opt_lower = opt_label.lower().strip()
            
            # Exact match
            if opt_lower == prior_lower or opt_value == prior_answer:
                return opt
            
            # Partial match (prior is substring of option or vice versa)
            if prior_lower in opt_lower or opt_lower in prior_lower:
                return opt
            
            # Numeric range matching
            if prior_mid is not None:
                opt_nums = [int(x) for x in re.findall(r'\d+', opt_label)]
                if opt_nums:
                    opt_mid = sum(opt_nums) / len(opt_nums)
                    distance = abs(opt_mid - prior_mid)
                    score = 1000 - distance  # Higher score = closer match
                    if score > best_score:
                        best_score = score
                        best_option = opt
        
        return best_option
    
    def check(
        self,
        persona_id: str,
        question_text: str,
        options: list[Any] | None = None,
    ) -> PinnedAnswer | None:
        """
        Check if a question has a pinned answer from prior history.
        
        Args:
            persona_id: Persona identifier
            question_text: The question text
            options: Available answer options (for closest-match finding)
            
        Returns:
            PinnedAnswer if category matches and prior exists, else None
        """
        category = self.categorize(question_text)
        if not category:
            return None
        
        prior_answers = self._get_prior_answers(persona_id, category)
        if not prior_answers:
            return None
        
        # Get most frequent answer
        most_frequent = max(prior_answers.items(), key=lambda x: x[1])
        answer_value = most_frequent[0]
        answer_count = most_frequent[1]
        total_count = sum(prior_answers.values())
        
        # If options provided, try to find closest match
        if options:
            closest = self._find_closest_option(answer_value, options)
            if closest:
                answer_value = closest.value if hasattr(closest, 'value') else str(closest)
        
        confidence = answer_count / total_count if total_count > 0 else 1.0
        
        return PinnedAnswer(
            category=category,
            value=answer_value,
            confidence=confidence,
            reasoning=f"Pinned from {answer_count}/{total_count} prior {category} answers (SR-152)",
        )
    
    def record_answer(
        self,
        persona_id: str,
        question_text: str,
        answer_value: str,
        question_hash: str,
    ) -> None:
        """
        Record an answer with its identity category (if applicable).
        
        Args:
            persona_id: Persona identifier
            question_text: The question text
            answer_value: The answer given
            question_hash: Hash of the question for consistency tracking
        """
        category = self.categorize(question_text)
        if not category:
            return
        
        if not self.db_path.exists():
            return
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                UPDATE answer_history
                SET identity_category = ?
                WHERE question_hash = ? AND persona_hash = ?
            """, (category, question_hash, persona_id))
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not update identity category: {e}")
        finally:
            conn.close()
    
    def scan(self, persona_id: str) -> dict[str, Contradiction]:
        """
        Scan a persona's answer history for contradictions.
        
        Args:
            persona_id: Persona identifier
            
        Returns:
            Dictionary of category -> Contradiction
        """
        results: dict[str, Contradiction] = {}
        
        for category in [
            IdentityCategory.AGE,
            IdentityCategory.GENDER,
            IdentityCategory.INCOME,
            IdentityCategory.EDUCATION,
            IdentityCategory.EMPLOYMENT,
            IdentityCategory.HOUSEHOLD_SIZE,
            IdentityCategory.COUNTRY,
        ]:
            answers = self._get_prior_answers(persona_id, category)
            
            if not answers:
                continue
            
            total = sum(answers.values())
            most_frequent = max(answers.items(), key=lambda x: x[1])
            
            results[category] = Contradiction(
                category=category,
                persona_id=persona_id,
                answers=answers,
                most_frequent=most_frequent[0],
                most_frequent_count=most_frequent[1],
                total_count=total,
                is_contradicted=len(answers) > 1,
            )
        
        return results
    
    def format_report(self, scan_results: dict[str, Contradiction]) -> str:
        """
        Format scan results as a human-readable report.
        
        Args:
            scan_results: Results from scan()
            
        Returns:
            Formatted report string
        """
        if not scan_results:
            return "No identity answers recorded for this persona."
        
        lines = []
        persona_id = next(iter(scan_results.values())).persona_id
        lines.append(f"Persona: {persona_id}")
        
        for category, contradiction in scan_results.items():
            status = "!! contradiction" if contradiction.is_contradicted else "ok consistent"
            
            # Format answer distribution
            answer_parts = []
            for answer, count in sorted(
                contradiction.answers.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                answer_parts.append(f'{count}x "{answer}"')
            
            answers_str = ", ".join(answer_parts)
            
            lines.append(
                f"  {category:15} {contradiction.total_count} answers, "
                f"{answers_str}  {status}"
            )
        
        return "\n".join(lines)
