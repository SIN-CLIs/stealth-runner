# Plan 07: AUTO-LOGIN HARDENING

> **Parent**: ULTIMATE-PLAN.md | **Phase**: 2 | **Priority**: P1
> **Effort**: 1.5 days | **Risk**: MEDIUM

---

## PROBLEM

1. **`execute()` defined TWICE** in `auto_google_login.py` (lines 341 and 1255) — shadow bug
2. **1734-line monolithic file** — impossible to test, understand, or modify
3. **No Keychain fallback** — if Keychain Auto-Fill disabled, login fails permanently
4. **Hardcoded email** in 4+ locations within the file
5. **Multiple `list_windows` calls** without caching between steps

## PLAN

### Step 1: Fix the shadow bug immediately

Delete the duplicate `execute()` at line 1255. Verify the one at line 341 is the correct version.

### Step 2: Refactor into auth module

```
survey_cli/auth/
├── google_oauth.py         ← 6-step flow, refactored from 1734 lines
├── login_verifier.py       ← CDP-based "Am I logged in?" check
├── keychain_fallback.py    ← NEW: Password-based fallback
└── oauth_detector.py       ← NEW: OAuth window detection + state tracking
```

### Step 3: Refactor `google_oauth.py`

Extract the monolithic `execute()` into composable steps:

```python
class GoogleOAuthFlow:
    """6-step Google OAuth login for HeyPiggy."""
    
    def __init__(self, cua_manager: DaemonManager):
        self.cua = cua_manager
    
    def is_already_logged_in(self) -> Optional[tuple]:
        """Step 0: Check if dashboard already shows login state."""
        ...
    
    def ensure_chrome(self, url) -> str:
        """Step 1: Start/inspect Chrome."""
        ...
    
    def click_google_login(self, pid, wid) -> bool:
        """Step 2-3: Find + click Google login symbol."""
        ...
    
    def fill_email(self, pid, wid, email) -> bool:
        """Step 4: Enter email + click Weiter."""
        ...
    
    def handle_keychain(self, pid, wid) -> bool:
        """Step 5: Keychain Fortfahren or password fallback."""
        ...
    
    def finalize_oauth(self, pid, wid) -> bool:
        """Step 6: Final Weiter + verify."""
        ...
    
    def execute(self, pid=None, url=None) -> Dict:
        """Orchestrate all 6 steps with retry on each."""
        ...
```

### Step 4: Implement Keychain fallback

```python
# survey_cli/auth/keychain_fallback.py
class KeychainFallback:
    """Password-based login when Keychain Auto-Fill is disabled."""
    
    def is_keychain_active(self, pid, wid) -> bool:
        """Detect if Keychain offered auto-fill."""
        ...
    
    def enter_password(self, pid, wid, password: str) -> bool:
        """Find password field + enter value + click next."""
        ...
```

### Step 5: Remove hardcoded email

Use `SecretsClient` from Plan 02:

```python
email = SecretsClient.get_google_email()
```

## DELIVERABLES

- [ ] Duplicate `execute()` deleted
- [ ] `survey_cli/auth/` module with refactored classes
- [ ] Keychain fallback implemented
- [ ] Email from SecretsClient
- [ ] Tests for each auth component

## VERIFICATION

```bash
# No duplicate execute
grep -c "def execute" survey_cli/auth/google_oauth.py  # = 1

# No hardcoded email in auth module
! grep -r "zukunftsorientierte" survey_cli/auth/

# Auth tests pass
pytest tests/unit/test_auth/ -v
```