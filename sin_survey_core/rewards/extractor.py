import re

def extract_eur_from_text(text):
    patterns = [
        r'(\d+[.,]\d{2})\s*[€]',
        r'[€]\s*(\d+[.,]\d{2})',
        r'EUR\s*[=:]\s*(\d+[.,]\d+)',
        r'(\d+[.,]\d{2})\s*EUR',
        r'Verdienst[s]?\s*[=:]?\s*(\d+[.,]\d{2})',
        r'Reward[s]?\s*[=:]?\s*(\d+[.,]\d{2})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(',', '.'))
    return 0.0

def extract_earnings_summary(page_text):
    eur = extract_eur_from_text(page_text)
    return {"eur": eur, "page_text": page_text[:200]}
