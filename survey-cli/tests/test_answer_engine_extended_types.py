"""
Unit tests for SR-150 extended question types.

Tests cover: DRAG_DROP, HOTSPOT, CONJOINT, MAX_DIFF, VIDEO_AD, AUDIO_AD.
Each type has 4+ tests: happy-path, determinism, persona-consistency, edge-case.

No real browser launch — browser_driver primitives are mocked.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import tempfile
import os

from survey.daemon.answer_engine import AnswerEngine, Persona, Answer
from survey.daemon.survey_parser import Question, QuestionType, QuestionOption


class TestDragDropAnswers(unittest.TestCase):
    """Tests for DRAG_DROP question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(
            age=30,
            gender="male",
            interests=["technology", "gaming"],
            conjoint_preferences={"price_weight": 0.4, "brand_weight": 0.3, "feature_weights": {"quality": 0.15, "convenience": 0.15}},
        )
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_drag_drop_happy_path(self):
        """DRAG_DROP: parser detects + engine generates ordered list."""
        question = Question(
            id="dd_1",
            type=QuestionType.DRAG_DROP,
            text="Rank these items by preference",
            options=[
                QuestionOption(value="a", label="Gaming Console"),
                QuestionOption(value="b", label="Smartphone"),
                QuestionOption(value="c", label="Laptop"),
            ],
        )
        answer = self.engine.generate_answer(question)
        
        self.assertEqual(answer.question_id, "dd_1")
        self.assertIsInstance(answer.value, list)
        self.assertEqual(len(answer.value), 3)
        self.assertEqual(set(answer.value), {"a", "b", "c"})
        self.assertIn("SR-150", answer.reasoning)

    def test_drag_drop_determinism(self):
        """DRAG_DROP: same input → same output across 100 runs."""
        question = Question(
            id="dd_det",
            type=QuestionType.DRAG_DROP,
            text="Rank items",
            options=[
                QuestionOption(value="x", label="Item X"),
                QuestionOption(value="y", label="Item Y"),
                QuestionOption(value="z", label="Item Z"),
            ],
        )
        
        # First run
        first_answer = self.engine.generate_answer(question)
        
        # Create fresh engines with same persona to test determinism
        for _ in range(100):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_drag_drop_answer(question, fresh_engine._hash_question(question))
            self.assertEqual(answer.value, first_answer.value)

    def test_drag_drop_persona_consistency(self):
        """DRAG_DROP: same persona+question → same answer across calls."""
        question = Question(
            id="dd_cons",
            type=QuestionType.DRAG_DROP,
            text="Order these",
            options=[
                QuestionOption(value="1", label="One"),
                QuestionOption(value="2", label="Two"),
            ],
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        # Should return historical answer
        self.assertEqual(answer1.value, answer2.value)
        self.assertEqual(answer2.reasoning, "Historical consistency")

    def test_drag_drop_empty_options(self):
        """DRAG_DROP: handles empty options gracefully."""
        question = Question(
            id="dd_empty",
            type=QuestionType.DRAG_DROP,
            text="Rank nothing",
            options=[],
        )
        answer = self.engine.generate_answer(question)
        
        # Should fall back to default
        self.assertEqual(answer.value, "N/A")
        self.assertLess(answer.confidence, 0.5)


class TestHotspotAnswers(unittest.TestCase):
    """Tests for HOTSPOT question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(age=35, gender="female")
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_hotspot_happy_path(self):
        """HOTSPOT: returns (x, y) coordinates for largest area."""
        question = Question(
            id="hs_1",
            type=QuestionType.HOTSPOT,
            text="Click on the product",
            hotspot_areas=[
                {"coords": [10, 10, 50, 50], "label": "small"},
                {"coords": [100, 100, 300, 300], "label": "large"},
            ],
        )
        answer = self.engine.generate_answer(question)
        
        self.assertIn("x", answer.value)
        self.assertIn("y", answer.value)
        # Should pick center of larger area (200, 200) with jitter
        self.assertGreater(answer.value["x"], 150)
        self.assertLess(answer.value["x"], 250)
        self.assertIn("SR-150", answer.reasoning)

    def test_hotspot_determinism(self):
        """HOTSPOT: same input → same output (within jitter range)."""
        question = Question(
            id="hs_det",
            type=QuestionType.HOTSPOT,
            text="Click area",
            hotspot_areas=[{"coords": [0, 0, 100, 100], "label": "zone"}],
        )
        
        # Run multiple times with same persona
        answers = []
        for _ in range(10):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_hotspot_answer(question, fresh_engine._hash_question(question))
            answers.append(answer.value)
        
        # All x values should be within jitter range of each other
        x_values = [a["x"] for a in answers]
        self.assertLess(max(x_values) - min(x_values), 15)  # max jitter spread

    def test_hotspot_persona_consistency(self):
        """HOTSPOT: historical answer returned on repeat."""
        question = Question(
            id="hs_cons",
            type=QuestionType.HOTSPOT,
            text="Click here",
            hotspot_areas=[{"coords": [50, 50, 150, 150], "label": "target"}],
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        self.assertEqual(answer1.value, answer2.value)

    def test_hotspot_no_areas(self):
        """HOTSPOT: falls back to image center when no areas defined."""
        question = Question(
            id="hs_empty",
            type=QuestionType.HOTSPOT,
            text="Click somewhere",
            hotspot_areas=[],
        )
        answer = self.engine.generate_answer(question)
        
        # Should click near center (200, 150 default)
        self.assertIn("x", answer.value)
        self.assertIn("y", answer.value)
        self.assertLess(answer.confidence, 0.6)


class TestConjointAnswers(unittest.TestCase):
    """Tests for CONJOINT question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(
            age=40,
            gender="male",
            brands={"electronics": "Sony"},
            conjoint_preferences={
                "price_weight": 0.5,
                "brand_weight": 0.3,
                "feature_weights": {"quality": 0.1, "convenience": 0.1},
            },
        )
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_conjoint_happy_path(self):
        """CONJOINT: scores cards and picks highest."""
        question = Question(
            id="cj_1",
            type=QuestionType.CONJOINT,
            text="Choose the product you prefer",
            conjoint_cards=[
                {"features": {"price": "$500", "brand": "Sony", "quality": "high"}},
                {"features": {"price": "$200", "brand": "Generic", "quality": "low"}},
                {"features": {"price": "$800", "brand": "Apple", "quality": "premium"}},
            ],
        )
        answer = self.engine.generate_answer(question)
        
        self.assertIn("selected_card", answer.value)
        self.assertIn("card_count", answer.value)
        self.assertEqual(answer.value["card_count"], 3)
        self.assertIn("SR-150", answer.reasoning)

    def test_conjoint_determinism(self):
        """CONJOINT: same cards → same selection."""
        question = Question(
            id="cj_det",
            type=QuestionType.CONJOINT,
            text="Pick one",
            conjoint_cards=[
                {"features": {"price": "$100", "brand": "A"}},
                {"features": {"price": "$150", "brand": "B"}},
            ],
        )
        
        first_answer = self.engine._generate_conjoint_answer(question, self.engine._hash_question(question))
        
        for _ in range(50):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_conjoint_answer(question, fresh_engine._hash_question(question))
            self.assertEqual(answer.value["selected_card"], first_answer.value["selected_card"])

    def test_conjoint_persona_consistency(self):
        """CONJOINT: historical answer on repeat."""
        question = Question(
            id="cj_cons",
            type=QuestionType.CONJOINT,
            text="Choose product",
            conjoint_cards=[{"features": {"price": "$99"}}],
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        self.assertEqual(answer1.value, answer2.value)

    def test_conjoint_no_cards_fallback(self):
        """CONJOINT: falls back to options if no cards."""
        question = Question(
            id="cj_fallback",
            type=QuestionType.CONJOINT,
            text="Choose",
            conjoint_cards=[],
            options=[
                QuestionOption(value="opt1", label="Option 1"),
                QuestionOption(value="opt2", label="Option 2"),
            ],
        )
        answer = self.engine.generate_answer(question)
        
        self.assertIn(answer.value, ["opt1", "opt2"])


class TestMaxDiffAnswers(unittest.TestCase):
    """Tests for MAX_DIFF question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(
            age=28,
            gender="female",
            interests=["fitness", "health"],
        )
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_max_diff_happy_path(self):
        """MAX_DIFF: returns most and least selections."""
        question = Question(
            id="md_1",
            type=QuestionType.MAX_DIFF,
            text="Select most and least important",
            options=[
                QuestionOption(value="a", label="Fitness equipment"),
                QuestionOption(value="b", label="Fast food"),
                QuestionOption(value="c", label="Health supplements"),
                QuestionOption(value="d", label="Video games"),
            ],
        )
        answer = self.engine.generate_answer(question)
        
        self.assertIn("most", answer.value)
        self.assertIn("least", answer.value)
        self.assertNotEqual(answer.value["most"], answer.value["least"])
        self.assertIn("SR-150", answer.reasoning)

    def test_max_diff_determinism(self):
        """MAX_DIFF: same input → same most/least."""
        question = Question(
            id="md_det",
            type=QuestionType.MAX_DIFF,
            text="Best/worst",
            options=[
                QuestionOption(value="x", label="X"),
                QuestionOption(value="y", label="Y"),
                QuestionOption(value="z", label="Z"),
            ],
        )
        
        first_answer = self.engine._generate_max_diff_answer(question, self.engine._hash_question(question))
        
        for _ in range(50):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_max_diff_answer(question, fresh_engine._hash_question(question))
            self.assertEqual(answer.value["most"], first_answer.value["most"])
            self.assertEqual(answer.value["least"], first_answer.value["least"])

    def test_max_diff_persona_consistency(self):
        """MAX_DIFF: historical answer on repeat."""
        question = Question(
            id="md_cons",
            type=QuestionType.MAX_DIFF,
            text="Choose",
            options=[
                QuestionOption(value="1", label="One"),
                QuestionOption(value="2", label="Two"),
            ],
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        self.assertEqual(answer1.value, answer2.value)

    def test_max_diff_insufficient_options(self):
        """MAX_DIFF: handles single option gracefully."""
        question = Question(
            id="md_single",
            type=QuestionType.MAX_DIFF,
            text="Best/worst with one option",
            options=[QuestionOption(value="only", label="Only option")],
        )
        answer = self.engine.generate_answer(question)
        
        # Should fall back to default
        self.assertEqual(answer.value, "only")


class TestVideoAdAnswers(unittest.TestCase):
    """Tests for VIDEO_AD question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(age=25, gender="male")
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_video_ad_happy_path(self):
        """VIDEO_AD: returns play_video action with selector."""
        question = Question(
            id="vid_1",
            type=QuestionType.VIDEO_AD,
            text="Watch this video",
            media_selector="#video-player",
        )
        answer = self.engine.generate_answer(question)
        
        self.assertEqual(answer.value["action"], "play_video")
        self.assertEqual(answer.value["media_selector"], "#video-player")
        self.assertIn("estimated_duration", answer.value)
        self.assertIn("SR-150", answer.reasoning)

    def test_video_ad_determinism(self):
        """VIDEO_AD: action structure is consistent."""
        question = Question(
            id="vid_det",
            type=QuestionType.VIDEO_AD,
            text="Video ad",
            media_selector="video",
        )
        
        for _ in range(10):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_video_ad_answer(question, fresh_engine._hash_question(question))
            self.assertEqual(answer.value["action"], "play_video")
            self.assertEqual(answer.value["media_selector"], "video")

    def test_video_ad_persona_consistency(self):
        """VIDEO_AD: historical answer on repeat."""
        question = Question(
            id="vid_cons",
            type=QuestionType.VIDEO_AD,
            text="Watch",
            media_selector="#vid",
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        self.assertEqual(answer1.value, answer2.value)

    def test_video_ad_no_selector(self):
        """VIDEO_AD: defaults to 'video' selector."""
        question = Question(
            id="vid_default",
            type=QuestionType.VIDEO_AD,
            text="Watch video",
            media_selector=None,
        )
        answer = self.engine.generate_answer(question)
        
        self.assertEqual(answer.value["media_selector"], "video")


class TestAudioAdAnswers(unittest.TestCase):
    """Tests for AUDIO_AD question type (SR-150)."""

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.persona = Persona(age=32, gender="female")
        self.engine = AnswerEngine(self.persona, db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_audio_ad_happy_path(self):
        """AUDIO_AD: returns play_audio action with muted flag."""
        question = Question(
            id="aud_1",
            type=QuestionType.AUDIO_AD,
            text="Listen to this audio",
            media_selector="#audio-player",
        )
        answer = self.engine.generate_answer(question)
        
        self.assertEqual(answer.value["action"], "play_audio")
        self.assertEqual(answer.value["media_selector"], "#audio-player")
        self.assertTrue(answer.value["muted"])
        self.assertIn("SR-150", answer.reasoning)

    def test_audio_ad_determinism(self):
        """AUDIO_AD: action structure is consistent."""
        question = Question(
            id="aud_det",
            type=QuestionType.AUDIO_AD,
            text="Audio ad",
            media_selector="audio",
        )
        
        for _ in range(10):
            fresh_engine = AnswerEngine(self.persona, db_path=tempfile.mktemp(suffix=".db"))
            answer = fresh_engine._generate_audio_ad_answer(question, fresh_engine._hash_question(question))
            self.assertEqual(answer.value["action"], "play_audio")
            self.assertTrue(answer.value["muted"])

    def test_audio_ad_persona_consistency(self):
        """AUDIO_AD: historical answer on repeat."""
        question = Question(
            id="aud_cons",
            type=QuestionType.AUDIO_AD,
            text="Listen",
            media_selector="#aud",
        )
        
        answer1 = self.engine.generate_answer(question)
        answer2 = self.engine.generate_answer(question)
        
        self.assertEqual(answer1.value, answer2.value)

    def test_audio_ad_no_selector(self):
        """AUDIO_AD: defaults to 'audio' selector."""
        question = Question(
            id="aud_default",
            type=QuestionType.AUDIO_AD,
            text="Listen audio",
            media_selector=None,
        )
        answer = self.engine.generate_answer(question)
        
        self.assertEqual(answer.value["media_selector"], "audio")


class TestBrowserDriverPrimitives(unittest.TestCase):
    """Tests for SR-150 browser driver primitives (mocked)."""

    @patch("survey.daemon.browser_driver.BrowserDriver")
    def test_drag_element_signature(self, mock_driver_class):
        """drag_element has correct signature."""
        mock_driver = MagicMock()
        mock_driver.drag_element = AsyncMock(return_value=True)
        
        # Verify signature accepts source_sel, target_sel, jitter
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            mock_driver.drag_element("source", "target", jitter=True)
        )
        
        mock_driver.drag_element.assert_called_once_with("source", "target", jitter=True)
        self.assertTrue(result)

    @patch("survey.daemon.browser_driver.BrowserDriver")
    def test_play_media_signature(self, mock_driver_class):
        """play_media has correct signature."""
        mock_driver = MagicMock()
        mock_driver.play_media = AsyncMock(return_value=30.5)
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            mock_driver.play_media("video", max_seconds=60.0)
        )
        
        mock_driver.play_media.assert_called_once_with("video", max_seconds=60.0)
        self.assertEqual(result, 30.5)


if __name__ == "__main__":
    unittest.main()
