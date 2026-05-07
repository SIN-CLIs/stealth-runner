"""Survey Filling Tool — __frozen__=True

Matches survey questions to user profile to prevent disqualification.

Usage:
    from tools.tool_fill_survey import SurveyFiller
    filler = SurveyFiller("jeremy_schulze")
    
    # Compact snapshot from NEMO
    snapshot = {
        "questions": ["Was ist Ihr Geschlecht?"],
        "options": [["Männlich", "Weiblich", "Divers"]],
        "input_fields": [],
    }
    
    actions = filler.decide_actions(snapshot)
    # -> [{"type": "radio", "question_idx": 0, "option_idx": 0, "reason": "profile.gender=male"}]

Profile keys:
    age, gender, gender_label, city, state, zip, street,
    household_size, marital_status, education, employment,
    employment_label, job_title, industry, household_income,
    personal_income, nationality, language, insurance_products,
    contracts, interests, vehicles, pets

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ skylight-cli click --element-index — Index instabil

KORREKT:
  ✅ --remote-allow-origins="*" (MIT Anführungszeichen)
  ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)"
  ✅ --force-renderer-accessibility
  ✅ NUR tool_*.py verwenden (nicht rohes cua-driver)
"""

from __future__ import annotations
import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

__frozen__ = True
__version__ = "2026-05-07"

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "survey", "profiles")


# ═══════════════════════════════════════════════════════════════════════════
# PROFILE LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_profile(name: str = "jeremy_schulze") -> Dict:
    """Load profile JSON and compute derived fields."""
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    with open(path) as f:
        profile = json.load(f)
    
    # Compute age from date_of_birth if present
    if "date_of_birth" in profile and not profile.get("age"):
        try:
            dob = datetime.strptime(profile["date_of_birth"], "%Y-%m-%d")
            profile["age"] = int((datetime.now() - dob).days / 365.25)
        except Exception:
            pass
    
    # Normalize keys for matching
    profile["_norm"] = {
        k: _normalize(v)
        for k, v in profile.items()
        if isinstance(v, str)
    }
    
    return profile


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation, strip."""
    return re.sub(r'[^\w\s]', '', text.lower()).strip()


def _similarity(a: str, b: str) -> float:
    """Fuzzy string similarity 0.0-1.0."""
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


# ═══════════════════════════════════════════════════════════════════════════
# QUESTION CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

QUESTION_PATTERNS = {
    "age": [
        r'alter', r'age', r'wie alt', r'jahr', r'geboren',
        r'altersgruppe', r'age group',
    ],
    "gender": [
        r'geschlecht', r'gender', r'sex', r'männlich', r'weiblich',
        r'ist ihr geschlecht',
    ],
    "city": [
        r'wohnen', r'wohnort', r'stadt', r'city', r'wohnhaft',
        r'in welcher stadt',
    ],
    "zip": [
        r'plz', r'postleitzahl', r'zip', r'postal',
    ],
    "state": [
        r'bundesland', r'land', r'state', r'province',
        r'in welchem bundesland',
    ],
    "income": [
        r'einkommen', r'income', r'verdienst', r'gehalt',
        r'haushaltseinkommen', r'household income',
        r'nettoeinkommen',
    ],
    "employment": [
        r'beruf', r'beschäftigung', r'employment', r'job',
        r'tätigkeit', r'arbeit', r'sind sie',
        r'was ist ihr beruf',
    ],
    "education": [
        r'bildung', r'education', r'schulabschluss', r'höchster',
        r'abschluss', r'studium', r'universität',
    ],
    "marital": [
        r'familienstand', r'marital', r'ledig', r'verheiratet',
        r'beziehung',
    ],
    "household_size": [
        r'haushalt', r'household', r'personen', r'leben.*haushalt',
        r'wie viele personen',
    ],
    "nationality": [
        r'staatsangehörigkeit', r'nationality', r'staatsbürgerschaft',
    ],
    "language": [
        r'sprache', r'language', r'muttersprache',
    ],
    "industry": [
        r'branche', r'industry', r'sektor', r'wirtschaftszweig',
    ],
    "job_title": [
        r'berufsbezeichnung', r'job title', r'position',
    ],
    "insurance": [
        r'versicherung', r'insurance', r'krankenversicherung',
        r'haftpflicht',
    ],
    "vehicle": [
        r'fahrzeug', r'vehicle', r'auto', r'pkw', r'motorrad',
        r'besitzen sie.*auto',
    ],
    "pets": [
        r'haustier', r'pet', r'hund', r'katze', r'tier',
    ],
    "interests": [
        r'interesse', r'interest', r'hobby',
    ],
    "contracts": [
        r'vertrag', r'contract', r'tarif', r'abo',
    ],
}


def classify_question(text: str) -> Optional[str]:
    """Classify a survey question text into a profile key."""
    text_lower = text.lower()
    scores = {}
    for key, patterns in QUESTION_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 1
        if score > 0:
            scores[key] = score
    
    if not scores:
        return None
    return max(scores, key=scores.get)


# ═══════════════════════════════════════════════════════════════════════════
# OPTION MATCHING
# ═══════════════════════════════════════════════════════════════════════════

def match_option(options: List[str], target: str, threshold: float = 0.6) -> Optional[int]:
    """Find best matching option index for target value.
    
    Returns:
        Index of best match, or None if no match above threshold.
    """
    best_idx, best_score = None, 0.0
    target_norm = _normalize(target)
    
    for i, option in enumerate(options):
        # Exact match
        if _normalize(option) == target_norm:
            return i
        
        # Fuzzy match
        score = _similarity(option, target)
        if score > best_score:
            best_score = score
            best_idx = i
    
    if best_score >= threshold:
        return best_idx
    return None


def match_income(options: List[str], income_bracket: str) -> Optional[int]:
    """Match income bracket like "3000-4000" to survey options.
    
    Options may be:
    - "unter 1000"
    - "1000 bis 2000"
    - "3000 bis 4000"
    - "mehr als 5000"
    """
    # Parse bracket
    m = re.match(r'(\d+)[\s-]+(\d+)', income_bracket)
    if not m:
        return match_option(options, income_bracket)
    low, high = int(m.group(1)), int(m.group(2))
    mid = (low + high) / 2
    
    best_idx, best_score = None, float('inf')
    for i, option in enumerate(options):
        # Extract numbers from option
        nums = re.findall(r'\d+', option.replace('.', '').replace(',', ''))
        if not nums:
            continue
        nums = [int(n) for n in nums]
        
        # Score by distance to mid
        if len(nums) == 1:
            # "unter 2000" or "mehr als 3000"
            dist = abs(nums[0] - mid)
        elif len(nums) >= 2:
            # "1000 bis 2000"
            opt_mid = (nums[0] + nums[1]) / 2
            dist = abs(opt_mid - mid)
        else:
            continue
        
        if dist < best_score:
            best_score = dist
            best_idx = i
    
    return best_idx


def match_age_bracket(options: List[str], age: int) -> Optional[int]:
    """Match age to bracket options like "16-25", "26-39", "40+".
    """
    best_idx, best_score = None, float('inf')
    
    for i, option in enumerate(options):
        # Try to parse bracket
        m = re.match(r'(\d+)[\s-]+(\d+)', option)
        if m:
            low, high = int(m.group(1)), int(m.group(2))
            if low <= age <= high:
                return i  # Exact match
            dist = min(abs(age - low), abs(age - high))
        else:
            # "unter 16", "ab 40", "40+", etc.
            nums = re.findall(r'\d+', option)
            if not nums:
                continue
            num = int(nums[0])
            if 'unter' in option.lower() or 'under' in option.lower():
                if age < num:
                    return i
                dist = age - num
            elif 'über' in option.lower() or 'over' in option.lower() or '+' in option:
                if age >= num:
                    return i
                dist = num - age
            else:
                dist = abs(age - num)
        
        if dist < best_score:
            best_score = dist
            best_idx = i
    
    return best_idx


# ═══════════════════════════════════════════════════════════════════════════
# SURVEY FILLER CLASS
# ═══════════════════════════════════════════════════════════════════════════

class SurveyFiller:
    """Fill survey questions using user profile."""
    
    def __init__(self, profile_name: str = "jeremy_schulze"):
        self.profile = load_profile(profile_name)
        self.questions_seen = []  # Track answered questions
    
    def decide_actions(self, snapshot: Dict) -> List[Dict]:
        """Decide actions for a compact snapshot.
        
        Args:
            snapshot: {"questions": [str], "options": [[str]], "input_fields": [str]}
        
        Returns:
            List of action dicts:
            [{"type": "radio", "question_idx": int, "option_idx": int, "reason": str}, ...]
        """
        actions = []
        questions = snapshot.get("questions", [])
        options_list = snapshot.get("options", [])
        inputs = snapshot.get("input_fields", [])
        
        for q_idx, question in enumerate(questions):
            key = classify_question(question)
            if not key:
                # Unknown question → skip or select first option
                actions.append({
                    "type": "unknown",
                    "question_idx": q_idx,
                    "reason": f"Unknown question: '{question[:50]}'",
                    "action": "skip",
                })
                continue
            
            # Get options for this question
            opts = options_list[q_idx] if q_idx < len(options_list) else []
            
            if key == "age":
                age = self.profile.get("age", 32)
                opt_idx = match_age_bracket(opts, age)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.age={age}",
                    })
            
            elif key == "gender":
                gender = self.profile.get("gender_label") or self.profile.get("gender", "")
                opt_idx = match_option(opts, gender)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.gender={gender}",
                    })
            
            elif key in ("city", "zip", "state", "street"):
                val = self.profile.get(key, "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio" if opts else "text",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "value": val,
                        "reason": f"profile.{key}={val}",
                    })
                elif not opts and inputs:
                    # Text input
                    actions.append({
                        "type": "text",
                        "question_idx": q_idx,
                        "value": val,
                        "reason": f"profile.{key}={val}",
                    })
            
            elif key == "income":
                income = self.profile.get("household_income") or self.profile.get("personal_income", "")
                if income:
                    opt_idx = match_income(opts, income)
                    if opt_idx is not None:
                        actions.append({
                            "type": "radio",
                            "question_idx": q_idx,
                            "option_idx": opt_idx,
                            "reason": f"profile.income={income}",
                        })
            
            elif key == "employment":
                val = self.profile.get("employment_label") or self.profile.get("employment", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.employment={val}",
                    })
            
            elif key == "education":
                val = self.profile.get("education", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.education={val}",
                    })
            
            elif key == "marital":
                val = self.profile.get("marital_status", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.marital={val}",
                    })
            
            elif key == "household_size":
                val = str(self.profile.get("household_size", ""))
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.household_size={val}",
                    })
            
            elif key == "nationality":
                val = self.profile.get("nationality", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.nationality={val}",
                    })
            
            elif key == "language":
                val = self.profile.get("language", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.language={val}",
                    })
            
            elif key == "industry":
                val = self.profile.get("industry", "")
                opt_idx = match_option(opts, val)
                if opt_idx is not None:
                    actions.append({
                        "type": "radio",
                        "question_idx": q_idx,
                        "option_idx": opt_idx,
                        "reason": f"profile.industry={val}",
                    })
            
            elif key == "insurance":
                vals = self.profile.get("insurance_products", [])
                matched = []
                for v in vals:
                    opt_idx = match_option(opts, v)
                    if opt_idx is not None:
                        matched.append(opt_idx)
                if matched:
                    actions.append({
                        "type": "checkbox",
                        "question_idx": q_idx,
                        "option_indices": matched,
                        "reason": f"profile.insurance={vals}",
                    })
            
            elif key == "vehicle":
                vals = self.profile.get("vehicles", [])
                matched = []
                for v in vals:
                    opt_idx = match_option(opts, v)
                    if opt_idx is not None:
                        matched.append(opt_idx)
                if matched:
                    actions.append({
                        "type": "checkbox",
                        "question_idx": q_idx,
                        "option_indices": matched,
                        "reason": f"profile.vehicles={vals}",
                    })
                else:
                    # No vehicle → maybe "kein" option
                    for i, opt in enumerate(opts):
                        if any(k in opt.lower() for k in ["kein", "nein", "nicht", "none", "no"]):
                            actions.append({
                                "type": "radio",
                                "question_idx": q_idx,
                                "option_idx": i,
                                "reason": "profile.vehicles=[] -> select 'kein'",
                            })
                            break
            
            elif key == "pets":
                vals = self.profile.get("pets", [])
                if not vals:
                    for i, opt in enumerate(opts):
                        if any(k in opt.lower() for k in ["kein", "nein", "nicht", "none", "no"]):
                            actions.append({
                                "type": "radio",
                                "question_idx": q_idx,
                                "option_idx": i,
                                "reason": "profile.pets=[] -> select 'kein'",
                            })
                            break
                else:
                    matched = []
                    for v in vals:
                        opt_idx = match_option(opts, v)
                        if opt_idx is not None:
                            matched.append(opt_idx)
                    if matched:
                        actions.append({
                            "type": "checkbox",
                            "question_idx": q_idx,
                            "option_indices": matched,
                            "reason": f"profile.pets={vals}",
                        })
            
            else:
                # Generic fallback
                val = self.profile.get(key, "")
                if val:
                    opt_idx = match_option(opts, str(val))
                    if opt_idx is not None:
                        actions.append({
                            "type": "radio",
                            "question_idx": q_idx,
                            "option_idx": opt_idx,
                            "reason": f"profile.{key}={val}",
                        })
        
        return actions
    
    def get_profile_value(self, key: str) -> Optional[str]:
        """Get raw profile value by key."""
        return self.profile.get(key)


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def decide_actions_for_snapshot(
    snapshot: Dict,
    profile_name: str = "jeremy_schulze",
) -> List[Dict]:
    """Convenience: create filler + decide in one call."""
    filler = SurveyFiller(profile_name)
    return filler.decide_actions(snapshot)


def match_single_option(
    question: str,
    options: List[str],
    profile_name: str = "jeremy_schulze",
) -> Optional[Dict]:
    """Match a single question to best option."""
    filler = SurveyFiller(profile_name)
    key = classify_question(question)
    if not key:
        return None
    
    # Get value from profile
    val = filler.get_profile_value(key)
    if not val:
        return None
    
    if key == "age" and isinstance(val, int):
        opt_idx = match_age_bracket(options, val)
    elif key == "income":
        opt_idx = match_income(options, str(val))
    else:
        opt_idx = match_option(options, str(val))
    
    if opt_idx is not None:
        return {
            "option_idx": opt_idx,
            "option_text": options[opt_idx],
            "profile_key": key,
            "profile_value": val,
        }
    return None


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ tool_fill_survey.py imported OK")
    print(f"  frozen={__frozen__}, version={__version__}")
    
    # Test classification
    assert classify_question("Was ist Ihr Geschlecht?") == "gender"
    assert classify_question("Wie alt sind Sie?") == "age"
    assert classify_question("In welchem Bundesland wohnen Sie?") == "state"
    assert classify_question("Was ist Ihr Haushaltseinkommen?") == "income"
    
    # Test age bracket matching
    opts = ["Unter 16", "16-25", "26-39", "40+"]
    assert match_age_bracket(opts, 32) == 2  # 26-39
    assert match_age_bracket(opts, 15) == 0  # Unter 16
    assert match_age_bracket(opts, 45) == 3  # 40+
    
    # Test income matching
    opts2 = ["unter 1000", "1000 bis 2000", "3000 bis 4000", "mehr als 5000"]
    assert match_income(opts2, "3000-4000") == 2
    
    # Test option matching
    opts3 = ["Männlich", "Weiblich", "Divers"]
    assert match_option(opts3, "Männlich") == 0
    assert match_option(opts3, "männlich") == 0  # case-insensitive
    
    # Test SurveyFiller with snapshot
    snapshot = {
        "questions": [
            "Was ist Ihr Geschlecht?",
            "Wie alt sind Sie?",
            "In welcher Stadt wohnen Sie?",
        ],
        "options": [
            ["Männlich", "Weiblich", "Divers"],
            ["Unter 16", "16-25", "26-39", "40+"],
            ["Berlin", "Hamburg", "München"],
        ],
        "input_fields": [],
    }
    
    filler = SurveyFiller("jeremy_schulze")
    actions = filler.decide_actions(snapshot)
    
    assert len(actions) == 3, f"Expected 3 actions, got {len(actions)}"
    assert actions[0]["type"] == "radio"
    assert actions[0]["option_idx"] == 0  # Männlich
    assert actions[1]["type"] == "radio"
    assert actions[1]["option_idx"] == 2  # 26-39 (age=32)
    assert actions[2]["type"] == "radio"
    assert actions[2]["option_idx"] == 0  # Berlin
    
    print("All tests passed")
    print(f"\nSample actions for test snapshot:")
    for a in actions:
        print(f"  {a}")