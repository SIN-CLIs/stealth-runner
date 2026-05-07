"""Test SOTA detection functions: detect_error_page, detect_progress, detect_completion.

WARUM: Fehler-Erkennung entscheidet über Abort vs. Retry.
Falsche Klassifizierung einer "Survey not available"-Seite als Fortschritt
verschwendet Aktionen und führt zu Blockierung.

ARCHITEKTUR: Unittest (keine Mocks nötig — pure Funktionen).
Tests rufen detect_error_page, detect_progress und detect_completion
mit statischen Strings auf und prüfen Regex/Keyword-Matching.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.execute import BatchExecutor
from survey.snapshot import detect_progress, detect_completion


class TestDetectErrorPage(unittest.TestCase):
    """Test BatchExecutor.detect_error_page() — comprehensive error detection."""

    def test_cpx_no_app_id(self):
        is_err, reason = BatchExecutor.detect_error_page("Error: No app id was specified")
        self.assertTrue(is_err)
        self.assertIn("CPX", reason)

    def test_cpx_survey_not_available(self):
        is_err, reason = BatchExecutor.detect_error_page("Survey not available - please return")
        self.assertTrue(is_err)
        self.assertIn("not available", reason)

    def test_purespectrum_unable_to_start(self):
        is_err, reason = BatchExecutor.detect_error_page("Error - unable to start survey")
        self.assertTrue(is_err)
        self.assertIn("expired", reason)

    def test_survey_link_expired(self):
        is_err, reason = BatchExecutor.detect_error_page("The survey link has expired")
        self.assertTrue(is_err)
        self.assertIn("expired", reason)

    def test_survey_has_ended(self):
        is_err, reason = BatchExecutor.detect_error_page("This survey has ended")
        self.assertTrue(is_err)
        self.assertIn("ended", reason)

    def test_survey_closed(self):
        is_err, reason = BatchExecutor.detect_error_page("Survey closed by researcher")
        self.assertTrue(is_err)
        self.assertIn("closed", reason)

    def test_umgeleitet(self):
        is_err, reason = BatchExecutor.detect_error_page("Sie werden umgeleitet...")
        self.assertTrue(is_err)
        self.assertIn("redirect", reason.lower())

    def test_redirect_generic(self):
        is_err, reason = BatchExecutor.detect_error_page("Redirecting you to the panel")
        self.assertTrue(is_err)
        self.assertIn("redirect", reason.lower())

    def test_error_occurred(self):
        is_err, reason = BatchExecutor.detect_error_page("An error occurred. Please try again.")
        self.assertTrue(is_err)
        self.assertIn("error", reason.lower())

    def test_german_error(self):
        is_err, reason = BatchExecutor.detect_error_page("Leider ist ein Fehler aufgetreten")
        self.assertTrue(is_err)
        self.assertIn("German", reason)

    def test_no_longer_available(self):
        is_err, reason = BatchExecutor.detect_error_page("This survey is no longer available")
        self.assertTrue(is_err)
        self.assertIn("available", reason.lower())

    def test_screen_out(self):
        is_err, reason = BatchExecutor.detect_error_page("Screen out - you do not qualify")
        self.assertTrue(is_err)
        self.assertIn("screen", reason.lower())

    def test_not_eligible(self):
        is_err, reason = BatchExecutor.detect_error_page("You are not eligible for this survey")
        self.assertTrue(is_err)
        self.assertIn("eligible", reason.lower())

    def test_not_qualify(self):
        is_err, reason = BatchExecutor.detect_error_page("You do not qualify for this survey")
        self.assertTrue(is_err)
        self.assertIn("qualify", reason.lower())

    def test_thank_you_interest(self):
        is_err, reason = BatchExecutor.detect_error_page("Thank you for your interest")
        self.assertTrue(is_err)
        self.assertIn("completed", reason.lower())

    def test_please_close_window(self):
        is_err, reason = BatchExecutor.detect_error_page("Please close this window and return")
        self.assertTrue(is_err)
        self.assertIn("completion", reason.lower())

    def test_return_to_panel(self):
        is_err, reason = BatchExecutor.detect_error_page("Please return to the panel")
        self.assertTrue(is_err)
        self.assertIn("screen", reason.lower())

    def test_limit_reached(self):
        is_err, reason = BatchExecutor.detect_error_page("You've reached the limit for today")
        self.assertTrue(is_err)
        self.assertIn("limit", reason.lower())

    def test_maximum_responses(self):
        is_err, reason = BatchExecutor.detect_error_page("Maximum number of responses reached")
        self.assertTrue(is_err)
        self.assertIn("full", reason.lower())

    def test_session_expired(self):
        is_err, reason = BatchExecutor.detect_error_page("Your session has expired. Please re-login.")
        self.assertTrue(is_err)
        self.assertIn("expired", reason.lower())

    def test_connection_error(self):
        is_err, reason = BatchExecutor.detect_error_page("Connection error - please try again")
        self.assertTrue(is_err)
        self.assertIn("connection", reason.lower())

    def test_technical_error(self):
        is_err, reason = BatchExecutor.detect_error_page("A technical error has occurred")
        self.assertTrue(is_err)
        self.assertIn("technical", reason.lower())

    def test_http_503(self):
        is_err, reason = BatchExecutor.detect_error_page("HTTP 503 Service Unavailable")
        self.assertTrue(is_err)
        self.assertIn("503", reason)

    def test_http_500(self):
        is_err, reason = BatchExecutor.detect_error_page("HTTP 500 Internal Server Error")
        self.assertTrue(is_err)
        self.assertIn("500", reason)

    def test_oops(self):
        is_err, reason = BatchExecutor.detect_error_page("Oops! Something went wrong")
        self.assertTrue(is_err)
        self.assertIn("Oops", reason)

    def test_sorry_error(self):
        is_err, reason = BatchExecutor.detect_error_page("Sorry, something went wrong")
        self.assertTrue(is_err)
        self.assertIn("sorry", reason.lower())

    def test_normal_survey_german(self):
        text = "Frage 1 von 10\nBitte wählen Sie eine Antwort:\n○ Männlich ○ Weiblich"
        is_err, reason = BatchExecutor.detect_error_page(text)
        self.assertFalse(is_err)
        self.assertEqual("", reason)

    def test_normal_survey_english(self):
        text = "Question 3 of 15\nHow often do you use this product?\n[daily] [weekly] [monthly]"
        is_err, reason = BatchExecutor.detect_error_page(text)
        self.assertFalse(is_err)

    def test_qualtrics_survey(self):
        text = "Next → Your progress: 2 / 20 questions answered"
        is_err, reason = BatchExecutor.detect_error_page(text)
        self.assertFalse(is_err)

    def test_loading_page(self):
        text = "Loading, please wait..."
        is_err, reason = BatchExecutor.detect_error_page(text)
        self.assertFalse(is_err)

    def test_empty_text(self):
        is_err, reason = BatchExecutor.detect_error_page("")
        self.assertFalse(is_err)

    def test_case_insensitive(self):
        is_err, reason = BatchExecutor.detect_error_page("NO APP ID WAS SPECIFIED")
        self.assertTrue(is_err)

    def test_partial_match_not_error(self):
        text = "Do you agree or disagree with this statement? (Error handling is important)"
        is_err, reason = BatchExecutor.detect_error_page(text)
        self.assertFalse(is_err)


class TestDetectProgress(unittest.TestCase):
    """Test detect_progress() — SOTA progress state detection."""

    def test_progress_3_of_10(self):
        progressed, status = detect_progress("Frage 3 von 10 — bitte auswählen")
        self.assertTrue(progressed)
        self.assertEqual("unknown", status)

    def test_progress_english(self):
        progressed, status = detect_progress("Question 5 of 20")
        self.assertTrue(progressed)
        self.assertEqual("unknown", status)

    def test_progress_percent_german(self):
        progressed, status = detect_progress("Fortschritt: 45% abgeschlossen")
        self.assertTrue(progressed)
        self.assertEqual("progressed", status)

    def test_progress_percent_english(self):
        progressed, status = detect_progress("Progress: 30% complete")
        self.assertTrue(progressed)
        self.assertEqual("progressed", status)

    def test_loading_page(self):
        progressed, status = detect_progress("Loading, just getting things ready...")
        self.assertFalse(progressed)
        self.assertEqual("loading", status)

    def test_loading_german(self):
        progressed, status = detect_progress("Bitte warten — wird geladen")
        self.assertFalse(progressed)
        self.assertEqual("loading", status)

    def test_error_page(self):
        progressed, status = detect_progress("Screen out - you do not qualify for this survey")
        self.assertFalse(progressed)
        self.assertEqual("error_page", status)

    def test_captcha(self):
        progressed, status = detect_progress("Bitte bestätigen: Ich bin kein Roboter")
        self.assertFalse(progressed)
        self.assertEqual("captcha", status)

    def test_captcha_english(self):
        progressed, status = detect_progress("Please verify: I am not a robot")
        self.assertFalse(progressed)
        self.assertEqual("captcha", status)

    def test_question_text_german(self):
        progressed, status = detect_progress("Wie oft nutzen Sie dieses Produkt?")
        self.assertTrue(progressed)

    def test_question_text_english(self):
        progressed, status = detect_progress("How often do you shop online?")
        self.assertTrue(progressed)

    def test_multiple_question_indicators(self):
        text = "Bitte auswählen:\n ○ Ja ○ Nein\nSind Sie mit folgenden einverstanden?"
        progressed, status = detect_progress(text)
        self.assertTrue(progressed)

    def test_radio_button_indicators(self):
        text = "Select your answer:\n○ Option 1\n○ Option 2\n○ Option 3"
        progressed, status = detect_progress(text)
        self.assertTrue(progressed)

    def test_empty_text(self):
        progressed, status = detect_progress("")
        self.assertTrue(progressed)


class TestDetectCompletion(unittest.TestCase):
    """Test detect_completion() — provider-specific completion detection."""

    def test_zurueck_zur_website(self):
        self.assertTrue(detect_completion("Zurück zur Website"))
        self.assertTrue(detect_completion("zurück zur website"))

    def test_gutgeschrieben(self):
        self.assertTrue(detect_completion("Guthaben wurde gutgeschrieben: 1,50 €"))
        self.assertTrue(detect_completion("gutgeschrieben"))

    def test_vielen_dank(self):
        self.assertTrue(detect_completion("Vielen Dank für das Ausfüllen der Umfrage!"))
        self.assertTrue(detect_completion("Vielen Dank für Ihre Teilnahme"))

    def test_danke_fuer(self):
        self.assertTrue(detect_completion("Danke fürs Mitmachen!"))
        self.assertTrue(detect_completion("danke für die umfrage"))

    def test_umfrage_beendet(self):
        self.assertTrue(detect_completion("Umfrage beendet"))
        self.assertTrue(detect_completion("umfrage beendet"))

    def test_abgeschlossen(self):
        self.assertTrue(detect_completion("Umfrage abgeschlossen"))
        self.assertTrue(detect_completion("abgeschlossen"))

    def test_erfolgreich(self):
        self.assertTrue(detect_completion("Erfolgreich abgeschlossen!"))
        self.assertTrue(detect_completion("erfolgreich"))

    def test_ausgefuellt(self):
        self.assertTrue(detect_completion("ausgefüllt"))

    def test_thank_you_completing(self):
        self.assertTrue(detect_completion("Thank you for completing this survey"))
        self.assertTrue(detect_completion("thank you for completing"))

    def test_thank_you_your(self):
        self.assertTrue(detect_completion("Thank you for your response"))
        self.assertTrue(detect_completion("thank you for your time"))

    def test_survey_complete(self):
        self.assertTrue(detect_completion("Survey complete"))
        self.assertTrue(detect_completion("survey complete"))

    def test_completed_the_survey(self):
        self.assertTrue(detect_completion("You have completed the survey"))
        self.assertTrue(detect_completion("completed the survey"))

    def test_successfully_submitted(self):
        self.assertTrue(detect_completion("Successfully submitted"))
        self.assertTrue(detect_completion("your response has been recorded"))

    def test_points_credited(self):
        self.assertTrue(detect_completion("Points have been credited to your account"))
        self.assertTrue(detect_completion("points credited"))

    def test_reward_credited(self):
        self.assertTrue(detect_completion("Reward credited"))
        self.assertTrue(detect_completion("reward credited"))

    def test_thank_you_participating(self):
        self.assertTrue(detect_completion("Thank you for participating"))
        self.assertTrue(detect_completion("thanks for completing"))

    def test_your_submission(self):
        self.assertTrue(detect_completion("Your submission has been received"))
        self.assertTrue(detect_completion("submitted successfully"))

    def test_finished(self):
        self.assertTrue(detect_completion("Finished!"))
        self.assertTrue(detect_completion("completed!"))

    def test_finished_checking(self):
        self.assertTrue(detect_completion("Finished checking your responses"))

    def test_survey_ended(self):
        self.assertTrue(detect_completion("survey has ended"))

    def test_question_page_not_completion(self):
        self.assertFalse(detect_completion("Question 3 of 15"))
        self.assertFalse(detect_completion("Wie lautet Ihre Meinung?"))
        self.assertFalse(detect_completion("Bitte auswählen:"))
        self.assertFalse(detect_completion("Next → Progress: 2/20"))

    def test_loading_page_not_completion(self):
        self.assertFalse(detect_completion("Loading please wait..."))

    def test_error_page_not_completion(self):
        self.assertFalse(detect_completion("No surveys available right now"))
        self.assertFalse(detect_completion("Screen out - you do not qualify"))

    def test_captcha_not_completion(self):
        self.assertFalse(detect_completion("Please verify: I am not a robot"))

    def test_empty_page_not_completion(self):
        self.assertFalse(detect_completion(""))

    def test_case_insensitive(self):
        self.assertTrue(detect_completion("THANK YOU FOR COMPLETING"))
        self.assertTrue(detect_completion("VIELEN DANK"))
        self.assertTrue(detect_completion("Survey Complete"))
        self.assertTrue(detect_completion("GUTGESCHRIEBEN"))

    def test_partial_keyword_in_question(self):
        self.assertFalse(detect_completion("How satisfied are you with the survey tool?"))
        self.assertFalse(detect_completion("Thank you for considering our offer"))


if __name__ == "__main__":
    unittest.main(verbosity=2)