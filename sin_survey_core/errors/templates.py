SURVEY_ERROR_PATTERNS = {
    "disqualified": [
        "we're sorry",
        "you did not qualify",
        "disqualif",
        "leider passen sie nicht",
        "not qualified",
    ],
    "quota_full": [
        "quota full",
        "survey has closed",
        "this survey is no longer available",
        "survey is full",
        "aktuell keine passende",
    ],
    "attention_failed": [
        "attention check",
        "quality trap",
        "failed quality check",
        "aufmerksamkeits",
    ],
    "not_found": [
        "we couldn't find a survey",
        "no survey available",
        "please try again later",
    ],
}

def classify_error(page_text):
    text_lower = page_text.lower()
    for error_type, patterns in SURVEY_ERROR_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return error_type
    return "unknown"
