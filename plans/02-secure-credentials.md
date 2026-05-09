# Plan 02: SECURE CREDENTIALS

> **Parent**: ULTIMATE-PLAN.md | **Phase**: 2 | **Priority**: P0
> **Effort**: 1 day | **Risk**: LOW

---

## PROBLEM

CPX API credentials (`app_id`, `ext_user_id`, `secure_hash`, email) are hardcoded in **4 files at 6 locations**:

| File | Lines |
|------|-------|
| `survey-cli/survey/chrome.py` | 89-94 |
| `survey-cli/tools/tool_open_survey.py` | 54-57 |
| `run_survey.py` | 166-171 |
| `src/stealth_survey/survey_agent.py` | 830-837 |

Email `zukunftsorientierte.energie@gmail.com` is in **4+ locations**.

## WHAT BREAKS

- Credential rotation requires code changes in 4 files
- Anyone with repo access gets full CPX API access
- `git clone` = full credential leak
- Pre-commit secret scanner would fail every commit

## PLAN

### Step 1: Centralize in SecretsClient

```python
# survey_cli/security/secrets.py
import os
from typing import Optional
from pydantic import BaseModel

class CPXCredentials(BaseModel):
    app_id: str
    ext_user_id: str
    secure_hash: str
    email: str

class SecretsClient:
    """Single source of truth for all credentials.
    
    Resolution order: env var → Infisical → ~/.stealth/config.yaml → error
    """
    
    @staticmethod
    def get_cpx_credentials() -> CPXCredentials:
        return CPXCredentials(
            app_id=os.getenv("CPX_APP_ID") or ...,
            ext_user_id=os.getenv("CPX_EXT_USER_ID") or ...,
            secure_hash=os.getenv("CPX_SECURE_HASH") or ...,
            email=os.getenv("CPX_EMAIL") or ...,
        )
    
    @staticmethod
    def get_nvidia_api_key() -> Optional[str]:
        return os.getenv("NVIDIA_API_KEY")
    
    @staticmethod
    def get_google_email() -> str:
        return os.getenv("GOOGLE_EMAIL", "")
```

### Step 2: Replace all 6 hardcoded locations

Each location replaces its inline credentials with:
```python
from survey_cli.security.secrets import SecretsClient
creds = SecretsClient.get_cpx_credentials()
```

### Step 3: Add secret scanner to pre-commit

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
  - id: detect-secrets
    args: ['--baseline', '.secrets.baseline']
```

### Step 4: Create `.env.example`

```bash
# .env.example (checked in)
CPX_APP_ID=
CPX_EXT_USER_ID=
CPX_SECURE_HASH=
CPX_EMAIL=
NVIDIA_API_KEY=nvapi-...
GOOGLE_EMAIL=
```

### Step 5: Git history cleanup

Use `git filter-branch` or BFG to remove credentials from git history. Rotate all credentials after cleanup.

## DELIVERABLES

- [ ] `SecretsClient` implemented
- [ ] All 6 credential locations migrated
- [ ] `.env.example` created
- [ ] Pre-commit secret scanner active
- [ ] Git history cleaned
- [ ] Credentials rotated

## VERIFICATION

```bash
# No hardcoded CPX values remain
! grep -r "11644" survey_cli/ survey-cli/ cli/ run_survey.py src/
! grep -r "ae75b0feca27c0f8eb356d7117d978ec" survey_cli/ survey-cli/ cli/ run_survey.py src/
! grep -r "2525530" survey_cli/ survey-cli/ cli/ run_survey.py src/

# SecretsClient used in all CPX consumers
grep -r "SecretsClient.get_cpx_credentials" survey_cli/ survey-cli/

# Pre-commit passes
pre-commit run --all-files
```