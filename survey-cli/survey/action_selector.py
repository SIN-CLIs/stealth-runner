"""ActionSelector — generate survey actions from CompactSnapshot when NIM unavailable.

WARUM: runner.py hatte 50+ Zeinen Fallback-Logik für den Fall dass NIM nicht
verfügbar ist. ActionSelector isoliert diese "einfache" Auswahl-Logik.

STRATEGIE:
  1. Erste ungewählte Radio/Checkbox → auswählen (Persona-Matching)
  2. Aktivierter Submit/Weiter-Button → klicken
  3. Textarea → mit plausibler Antwort füllen

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
"""

from typing import List, Dict, Any


class ActionSelector:
    """Select actions from a CompactSnapshot using heuristics (no LLM)."""

    # Preferred persona keywords for German surveys
    PREFERRED_ANSWERS = [
        "berlin", "männlich", "weiblich", "deutsch",
        "angestellt", "verheiratet", "mittlere", "master",
    ]

    # Submit button keywords (German + English)
    SUBMIT_KEYWORDS = [
        "weiter", "next", "submit", "nächste", "forward", "fortfahren",
    ]

    @classmethod
    def select_actions(cls, snapshot) -> List[Dict[str, Any]]:
        """Generate action list from snapshot (fallback when NIM unavailable).

        Args:
            snapshot: CompactSnapshot with .refs dict

        Returns:
            List of action dicts, max 2 items.
        """
        actions = []

        # 1. Select first unchecked radio/checkbox (prefer persona answers)
        selected = cls._select_radio(snapshot)
        if selected:
            actions.append(selected)

        # 2. Find enabled submit/next button
        submit = cls._find_submit(snapshot)
        if submit:
            actions.append(submit)
        else:
            # 3. No submit — maybe open-ended textarea
            text = cls._fill_textarea(snapshot)
            if text:
                actions.append(text)

        # Safety cap: never return more than 2 actions
        return actions[:2]

    @classmethod
    def _select_radio(cls, snapshot):
        """Return select action for best radio/checkbox match."""
        refs = getattr(snapshot, "refs", {})

        # First pass: prefer persona answers
        for ref, info in refs.items():
            role = info.get("role", "")
            if role in ("radio", "checkbox") and info.get("enabled", True):
                text = info.get("text", "").lower()
                if any(p in text for p in cls.PREFERRED_ANSWERS):
                    return {"ref": ref, "action": "select"}

        # Second pass: first available
        for ref, info in refs.items():
            if info.get("role") in ("radio", "checkbox") and info.get("enabled", True):
                return {"ref": ref, "action": "select"}

        return None

    @classmethod
    def _find_submit(cls, snapshot):
        """Return submit action for first enabled submit button."""
        refs = getattr(snapshot, "refs", {})
        for ref, info in refs.items():
            if info.get("role") == "button":
                text = info.get("text", "").lower()
                enabled = info.get("enabled", True)
                if enabled and any(kw in text for kw in cls.SUBMIT_KEYWORDS):
                    return {"action": "submit"}
        return None

    @classmethod
    def _fill_textarea(cls, snapshot):
        """Return fill action for first textarea with plausible answer."""
        refs = getattr(snapshot, "refs", {})
        for ref, info in refs.items():
            if info.get("role") == "textbox":
                placeholder = info.get("placeholder", "").lower()
                if "gemüse" in placeholder or "hobby" in placeholder:
                    return {
                        "ref": ref, "action": "fill",
                        "value": "Karotten werden von vielen Menschen gegessen, weil sie gesund und vielseitig sind.",  # noqa: E501
                    }
                elif "beschreiben" in placeholder:
                    return {
                        "ref": ref, "action": "fill",
                        "value": "Ich finde das Thema interessant und nehme gerne an Umfragen teil.",  # noqa: E501
                    }
                else:
                    return {"ref": ref, "action": "fill", "value": "Ja"}
        return None
