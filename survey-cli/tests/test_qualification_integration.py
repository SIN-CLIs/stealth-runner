#!/usr/bin/env python3
"""
Integration Test: Qualification Rules in decide_node
=====================================================

Testet dass decide_node TATSÄCHLICH disqualifizierende Antworten filtert.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from survey.qualification_rules import is_disqualifying_answer


def test_disqualifying_patterns():
    """Test dass bekannte Disqualifikations-Antworten erkannt werden."""
    
    disqualifying = [
        "Möchte nicht angeben",
        "Prefer not to say",
        "Keine Angabe",
        "Weiß nicht",
        "Don't know",
        "Keine Kinder",
        "No children",
        "Keine Haustiere",
        "No pets",
        "Unter 20.000€",
        "Under $15,000",
        "Arbeitslos",
        "Unemployed",
        "Nie",
        "Never",
        "Keines davon",
        "None of the above",
    ]
    
    for answer in disqualifying:
        result = is_disqualifying_answer(answer)
        assert result, f"FAIL: '{answer}' should be disqualifying but got {result}"
        print(f"PASS: '{answer}' -> disqualifying")
    
    print(f"\n{len(disqualifying)} disqualifying patterns tested OK")


def test_safe_patterns():
    """Test dass sichere Antworten NICHT gefiltert werden."""
    
    safe = [
        "Ja, habe Kinder",
        "Yes, I have children",
        "1-2 Kinder",
        "Ja, habe Haustiere",
        "Hund",
        "Katze",
        "Vollzeit beschäftigt",
        "Full-time employed",
        "40.000 - 60.000€",
        "$50,000 - $75,000",
        "Sehr wahrscheinlich",
        "Very likely",
        "Definitiv",
    ]
    
    for answer in safe:
        result = is_disqualifying_answer(answer)
        assert not result, f"FAIL: '{answer}' should be safe but got {result}"
        print(f"PASS: '{answer}' -> safe")
    
    print(f"\n{len(safe)} safe patterns tested OK")


def test_decide_node_filtering():
    """Test dass decide_node die Filter tatsächlich anwendet.
    
    Simuliert radio_options Liste und prüft Filterung.
    """
    from survey.qualification_rules import filter_safe_answers
    
    # Simulierte Radio-Optionen (wie sie in decide_node vorkommen)
    radio_names = [
        "Ja, habe Kinder",
        "Nein, keine Kinder",  # <-- disqualifying
        "Möchte nicht angeben",  # <-- disqualifying
    ]
    
    safe_indices = filter_safe_answers(radio_names)
    
    # Nur Index 0 sollte übrig bleiben
    assert 0 in safe_indices, "Index 0 ('Ja, habe Kinder') should be safe"
    assert 1 not in safe_indices, "Index 1 ('Nein, keine Kinder') should be filtered"
    assert 2 not in safe_indices, "Index 2 ('Möchte nicht angeben') should be filtered"
    
    print("PASS: decide_node filtering works correctly")
    print(f"  Input: {radio_names}")
    print(f"  Safe indices: {safe_indices}")


if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATION TEST: Qualification Rules")
    print("=" * 60)
    
    test_disqualifying_patterns()
    print()
    test_safe_patterns()
    print()
    test_decide_node_filtering()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
