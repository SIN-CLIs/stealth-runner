# Plan SR-33: Persona System

## Profile Class

```python
# cli/modules/persona.py

import json, os
from datetime import date
from pathlib import Path

PROFILE_DIR = Path(__file__).parent.parent.parent / "config" / "profiles"

class Profile:
    def __init__(self, profile_name: str):
        path = PROFILE_DIR / f"{profile_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")
        self.data = json.loads(path.read_text())
        self.name = profile_name
    
    @classmethod
    def load(cls, name: str) -> 'Profile':
        return cls(name)
    
    # -- Computed Properties --
    
    @property
    def age(self) -> int:
        """Calculate current age from date_of_birth."""
        dob = self.data['date_of_birth']  # "1993-11-13"
        born = date.fromisoformat(dob)
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    
    @property
    def gender_label(self) -> str:
        return "Männlich" if self.data['gender'] == 'male' else "Weiblich"
    
    @property
    def state_label(self) -> str:
        return self.data['state']  # "Berlin"
    
    @property
    def employment_label(self) -> str:
        mapping = {
            'employed_fulltime': 'Angestellte',
            'self_employed': 'Selbständig',
            'student': 'Student',
            'retired': 'Rentner',
            'unemployed': 'Zur Zeit nicht berufstätig',
        }
        return mapping.get(self.data.get('employment', ''), 'Angestellte')
    
    @property
    def education_label(self) -> str:
        mapping = {
            'none': 'Vorzeitig ohne Abschluss',
            'hauptschule': 'Haupt-/Volksschule',
            'realschule': 'Realschule, Mittlere Reife',
            'abitur': '(Fach-)Hochschulreife (Abitur)',
            'hochschule': '(Fach-)Hochschulabschluss',
        }
        return mapping.get(self.data.get('education', ''), 'Abitur')
    
    @property
    def marital_status_label(self) -> str:
        mapping = {
            'married': 'Verheiratet oder eingetragene Lebenspartnerschaft',
            'relationship': 'In Beziehung lebend',
            'single': 'Ledig oder Single',
            'widowed': 'Verwitwet',
            'divorced': 'Geschieden',
        }
        return mapping.get(self.data.get('marital_status', ''), 'Ledig')
    
    @property
    def household_income_label(self) -> str:
        return self.data.get('household_income', '3000-4000')
    
    @property
    def personal_income_label(self) -> str:
        return self.data.get('personal_income', '1000-2000')
    
    @property
    def household_size(self) -> int:
        return self.data.get('household_size', 3)
    
    # -- Question Resolution --
    
    QUESTION_KEYWORDS = {
        'alter': 'age',
        'jahre': 'age',
        'geschlecht': 'gender',
        'sind sie': 'gender',
        'bundesland': 'state',
        'wohnort': 'city',
        'beruf': 'employment',
        'tätigkeit': 'employment',
        'schulabschluss': 'education',
        'bildung': 'education',
        'einkommen': 'income',
        'haushalt': 'household_size',
        'personen': 'household_size',
        'familienstand': 'marital_status',
        'versicherung': 'insurance',
        'vertrag': 'contracts',
    }
    
    def resolve_answer(self, question_text: str, options: list) -> int:
        """Find the matching option index for a question."""
        q_lower = question_text.lower()
        
        # Determine what the question is about
        field = None
        for keyword, f in self.QUESTION_KEYWORDS.items():
            if keyword in q_lower:
                field = f
                break
        
        if field == 'age':
            age_bracket = self._get_age_bracket()
            for i, opt in enumerate(options):
                if age_bracket in opt:
                    return i
        
        elif field == 'gender':
            gender = self.gender_label.lower()
            for i, opt in enumerate(options):
                if gender in opt.lower():
                    return i
        
        elif field == 'state':
            state = self.state_label.lower()
            for i, opt in enumerate(options):
                if state in opt.lower():
                    return i
        
        elif field == 'education':
            edu = self.education_label.lower()
            for i, opt in enumerate(options):
                if 'abitur' in opt.lower() or 'hochschulreife' in opt.lower():
                    return i  # Prefer Abitur over Universität (avoids screen-out)
        
        elif field == 'employment':
            emp = self.employment_label.lower()
            for i, opt in enumerate(options):
                if emp in opt.lower():
                    return i
        
        elif field == 'income':
            inc = self.household_income_label
            for i, opt in enumerate(options):
                if inc in opt:
                    return i
        
        # Default: return first option
        return 0
    
    def _get_age_bracket(self) -> str:
        """Map age to Qualtrics bracket."""
        age = self.age
        if age < 18: return "Unter 18"
        elif age <= 19: return "18 bis 19"
        elif age <= 25: return "20 bis 25"
        elif age <= 30: return "26 bis 30"
        elif age <= 35: return "31 bis 35"
        elif age <= 40: return "36 bis 40"
        elif age <= 45: return "41 bis 45"
        return "46 bis 50"
```

## usage

```python
# run_survey.py
from cli.modules.persona import Profile

persona = Profile.load("jeremy_schulze")

# survey_cdp.py
def fill_demographics(ws, persona, provider_pattern):
    question = get_question_text(ws)
    options = get_options(ws, provider_pattern)
    answer_idx = persona.resolve_answer(question, options)
    if answer_idx is not None:
        answer_radio(ws, answer_idx)
        click_next(ws, provider_pattern)
```

## Implementation: ~1.5h
