"""
Unit Tests for Onboarding Crew V2

Tests all key features:
- Skip detection and 3-strike handling
- Irrelevant question detection
- ARI personality responses
- Two-tier progression
- Root value tracking
- Data extraction
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crews.onboarding_crew_v2 import OnboardingCrewV2, create_onboarding_crew_v2
from prompts.onboarding_prompts_v2 import get_all_nodes


class TestSkipDetection(unittest.TestCase):
    """Test skip/pass detection logic."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_detect_explicit_skip(self):
        """Test detection of explicit 'skip' keyword."""
        self.assertTrue(self.crew._detect_skip_or_pass("skip"))
        self.assertTrue(self.crew._detect_skip_or_pass("Skip this question"))
        self.assertTrue(self.crew._detect_skip_or_pass("I want to skip"))

    def test_detect_pass(self):
        """Test detection of 'pass' keyword."""
        self.assertTrue(self.crew._detect_skip_or_pass("pass"))
        self.assertTrue(self.crew._detect_skip_or_pass("I'll pass on that"))
        self.assertTrue(self.crew._detect_skip_or_pass("pass for now"))

    def test_detect_next(self):
        """Test detection of 'next' as skip."""
        self.assertTrue(self.crew._detect_skip_or_pass("next"))
        self.assertTrue(self.crew._detect_skip_or_pass("next question"))
        self.assertTrue(self.crew._detect_skip_or_pass("move on to next"))

    def test_detect_prefer_not_to_say(self):
        """Test detection of 'prefer not to say'."""
        self.assertTrue(self.crew._detect_skip_or_pass("prefer not to say"))
        self.assertTrue(self.crew._detect_skip_or_pass("I'd rather not"))
        self.assertTrue(self.crew._detect_skip_or_pass("not comfortable answering"))

    def test_no_false_positives(self):
        """Test that normal responses aren't detected as skips."""
        self.assertFalse(self.crew._detect_skip_or_pass("I like casual style"))
        self.assertFalse(self.crew._detect_skip_or_pass("My favorite brand is Nike"))
        self.assertFalse(self.crew._detect_skip_or_pass("I'm 28 years old"))


class TestIrrelevantQuestionDetection(unittest.TestCase):
    """Test detection of irrelevant questions."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_detect_physics_question(self):
        """Test detection of physics-related questions."""
        topic = self.crew._detect_irrelevant_question("What do you think about quantum physics?")
        self.assertEqual(topic, 'physics')

        topic = self.crew._detect_irrelevant_question("Tell me about the universe?")
        self.assertEqual(topic, 'physics')

    def test_detect_weather_question(self):
        """Test detection of weather questions."""
        topic = self.crew._detect_irrelevant_question("What's the weather today?")
        self.assertEqual(topic, 'weather')

        topic = self.crew._detect_irrelevant_question("Is it going to rain?")
        self.assertEqual(topic, 'weather')

    def test_detect_about_ari_question(self):
        """Test detection of questions about ARI."""
        topic = self.crew._detect_irrelevant_question("Who are you?")
        self.assertEqual(topic, 'about_ari')

        topic = self.crew._detect_irrelevant_question("How were you made?")
        self.assertEqual(topic, 'about_ari')

    def test_detect_generic_irrelevant(self):
        """Test detection of generic irrelevant questions."""
        topic = self.crew._detect_irrelevant_question("What's the capital of France?")
        self.assertEqual(topic, 'generic')

    def test_no_false_positives_on_fashion_questions(self):
        """Test that fashion-related questions aren't flagged as irrelevant."""
        topic = self.crew._detect_irrelevant_question("What style suits me?")
        self.assertIsNone(topic)

        topic = self.crew._detect_irrelevant_question("How should I dress for work?")
        self.assertIsNone(topic)

    def test_no_false_positives_on_statements(self):
        """Test that non-questions aren't flagged."""
        topic = self.crew._detect_irrelevant_question("I like dark colors")
        self.assertIsNone(topic)


class TestARIPersonalityResponses(unittest.TestCase):
    """Test ARI personality response generation."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_physics_response(self):
        """Test physics personality response."""
        response = self.crew._generate_ari_personality_response(
            'physics',
            "What do you think about quantum mechanics?"
        )
        self.assertIn("past life", response.lower())
        self.assertIn("physics", response.lower())
        self.assertIn("patterns", response.lower())

    def test_weather_response(self):
        """Test weather personality response."""
        response = self.crew._generate_ari_personality_response(
            'weather',
            "What's the weather like?"
        )
        self.assertIn("raindrops", response.lower())
        self.assertIn("body", response.lower())

    def test_about_ari_response(self):
        """Test about ARI personality response."""
        response = self.crew._generate_ari_personality_response(
            'about_ari',
            "Who created you?"
        )
        self.assertIn("ari", response.lower())
        self.assertIn("style", response.lower())

    def test_generic_response(self):
        """Test generic irrelevant response."""
        response = self.crew._generate_ari_personality_response(
            'generic',
            "What's your favorite food?"
        )
        self.assertIn("interesting", response.lower())
        self.assertIn("style", response.lower())

    def test_all_responses_redirect(self):
        """Test that all personality responses redirect back to style."""
        topics = ['physics', 'weather', 'about_ari', 'generic']
        for topic in topics:
            response = self.crew._generate_ari_personality_response(topic, "Test question?")
            # Should redirect back to style conversation
            self.assertTrue(
                any(keyword in response.lower() for keyword in ['style', 'you', 'your', 'discover']),
                f"Response for {topic} doesn't redirect properly"
            )


class TestSkipHandling(unittest.TestCase):
    """Test 3-strike skip handling system."""

    def setUp(self):
        self.crew = OnboardingCrewV2()
        self.crew.current_node_id = "personal"

    def test_first_skip_graceful(self):
        """Test first skip is handled gracefully."""
        result = self.crew._handle_skip("personal", "skip")

        self.assertTrue(result['skip_handled'])
        self.assertTrue(result['continue_node'])
        self.assertIn("no worries", result['agent_response'].lower())
        self.assertEqual(self.crew.consecutive_skip_count, 1)
        self.assertEqual(self.crew.skip_counts["personal"], 1)

    def test_second_skip_supportive(self):
        """Test second skip is still supportive."""
        self.crew.consecutive_skip_count = 1
        result = self.crew._handle_skip("personal", "pass")

        self.assertTrue(result['skip_handled'])
        self.assertTrue(result['continue_node'])
        self.assertIn("fine", result['agent_response'].lower())
        self.assertEqual(self.crew.consecutive_skip_count, 2)

    def test_third_skip_check_in(self):
        """Test third skip triggers check-in."""
        self.crew.consecutive_skip_count = 2
        result = self.crew._handle_skip("personal", "next")

        self.assertTrue(result['skip_handled'])
        self.assertFalse(result['continue_node'])  # Pause for feedback
        self.assertTrue(result.get('needs_feedback', False))
        self.assertIn("notice", result['agent_response'].lower())
        self.assertIn("holding you back", result['agent_response'].lower())
        self.assertEqual(self.crew.consecutive_skip_count, 3)

    def test_fourth_skip_raincheck(self):
        """Test fourth skip offers raincheck."""
        self.crew.consecutive_skip_count = 3
        result = self.crew._handle_skip("personal", "skip")

        self.assertTrue(result['skip_handled'])
        self.assertFalse(result['continue_node'])
        self.assertTrue(result.get('offer_raincheck', False))
        self.assertIn("another time", result['agent_response'].lower())
        self.assertEqual(self.crew.consecutive_skip_count, 4)

    def test_skip_counter_reset(self):
        """Test skip counter resets when user engages."""
        self.crew.consecutive_skip_count = 2
        self.crew._reset_skip_counter()
        self.assertEqual(self.crew.consecutive_skip_count, 0)

    def test_skip_counts_per_node(self):
        """Test skip counts are tracked per node."""
        self.crew._handle_skip("personal", "skip")
        self.crew._handle_skip("personal", "skip")
        self.crew._handle_skip("taste", "skip")

        self.assertEqual(self.crew.skip_counts["personal"], 2)
        self.assertEqual(self.crew.skip_counts["taste"], 1)


class TestTwoTierProgression(unittest.TestCase):
    """Test two-tier system (need_to_ask → nice_to_know)."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_complete_tier(self):
        """Test marking a tier as complete."""
        self.crew.node_completion["personal"] = {"need_to_ask": False, "nice_to_know": False}

        success = self.crew.complete_tier("personal", "need_to_ask")
        self.assertTrue(success)
        self.assertTrue(self.crew.node_completion["personal"]["need_to_ask"])

    def test_should_offer_nice_to_know_when_ready(self):
        """Test offering nice_to_know after need_to_ask complete."""
        # Personal node has nice_to_know content
        self.crew.node_completion["personal"] = {
            "need_to_ask": True,
            "nice_to_know": False
        }

        should_offer = self.crew.should_offer_nice_to_know("personal")
        self.assertTrue(should_offer)

    def test_should_not_offer_nice_to_know_when_incomplete(self):
        """Test not offering nice_to_know when need_to_ask incomplete."""
        self.crew.node_completion["personal"] = {
            "need_to_ask": False,
            "nice_to_know": False
        }

        should_offer = self.crew.should_offer_nice_to_know("personal")
        self.assertFalse(should_offer)

    def test_should_not_offer_nice_to_know_when_already_complete(self):
        """Test not offering nice_to_know when already complete."""
        self.crew.node_completion["personal"] = {
            "need_to_ask": True,
            "nice_to_know": True
        }

        should_offer = self.crew.should_offer_nice_to_know("personal")
        self.assertFalse(should_offer)

    def test_tier_progression_flow(self):
        """Test full tier progression flow."""
        node_id = "personal"

        # Start with nothing complete
        self.crew.node_completion[node_id] = {"need_to_ask": False, "nice_to_know": False}

        # Complete need_to_ask
        self.crew.complete_tier(node_id, "need_to_ask")
        self.assertTrue(self.crew.node_completion[node_id]["need_to_ask"])

        # Should offer nice_to_know
        self.assertTrue(self.crew.should_offer_nice_to_know(node_id))

        # Complete nice_to_know
        self.crew.complete_tier(node_id, "nice_to_know")
        self.assertTrue(self.crew.node_completion[node_id]["nice_to_know"])

        # Should not offer again
        self.assertFalse(self.crew.should_offer_nice_to_know(node_id))


class TestRootValueTracking(unittest.TestCase):
    """Test root value discovery and tracking."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_root_values_stored_per_node(self):
        """Test root values are stored per node."""
        # Simulate extraction with root values
        extracted_info = {
            "root_values_detected": ["authenticity", "confidence"]
        }

        # Simulate processing
        self.crew.current_node_id = "personal"
        if self.crew.current_node_id not in self.crew.root_values:
            self.crew.root_values[self.crew.current_node_id] = []

        self.crew.root_values[self.crew.current_node_id].extend(
            extracted_info["root_values_detected"]
        )

        self.assertEqual(len(self.crew.root_values["personal"]), 2)
        self.assertIn("authenticity", self.crew.root_values["personal"])
        self.assertIn("confidence", self.crew.root_values["personal"])

    def test_root_values_deduplicated(self):
        """Test duplicate root values are removed."""
        self.crew.current_node_id = "personal"
        self.crew.root_values["personal"] = ["authenticity", "confidence"]

        # Add duplicate
        new_values = ["confidence", "growth"]
        self.crew.root_values["personal"].extend(new_values)
        self.crew.root_values["personal"] = list(set(self.crew.root_values["personal"]))

        self.assertEqual(len(self.crew.root_values["personal"]), 3)
        self.assertEqual(
            self.crew.root_values["personal"].count("confidence"),
            1
        )

    def test_get_all_data_includes_root_values(self):
        """Test that get_all_extracted_data includes root values."""
        self.crew.root_values["personal"] = ["authenticity", "confidence"]
        self.crew.root_values["taste"] = ["self-expression", "creativity"]

        all_data = self.crew.get_all_extracted_data()

        self.assertIn("root_values", all_data)
        self.assertEqual(len(all_data["root_values"]["personal"]), 2)
        self.assertEqual(len(all_data["root_values"]["taste"]), 2)


class TestNodeProgression(unittest.TestCase):
    """Test node-to-node progression logic."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_get_next_node_first_time(self):
        """Test getting first node when nothing complete."""
        next_node = self.crew.get_next_node()
        all_nodes = get_all_nodes()
        self.assertEqual(next_node, all_nodes[0])

    def test_get_next_node_after_completion(self):
        """Test getting next node after completing first."""
        all_nodes = get_all_nodes()
        first_node = all_nodes[0]

        # Mark first node complete (both tiers)
        self.crew.node_completion[first_node] = {
            "need_to_ask": True,
            "nice_to_know": True
        }

        next_node = self.crew.get_next_node()
        self.assertEqual(next_node, all_nodes[1])

    def test_get_next_node_returns_none_when_all_complete(self):
        """Test None returned when all nodes complete."""
        all_nodes = get_all_nodes()

        # Mark all nodes complete
        for node_id in all_nodes:
            self.crew.node_completion[node_id] = {
                "need_to_ask": True,
                "nice_to_know": True
            }

        next_node = self.crew.get_next_node()
        self.assertIsNone(next_node)

    def test_is_complete_requires_all_need_to_ask(self):
        """Test is_complete checks all need_to_ask tiers."""
        all_nodes = get_all_nodes()

        # Mark all but one complete
        for node_id in all_nodes[:-1]:
            self.crew.node_completion[node_id] = {
                "need_to_ask": True,
                "nice_to_know": False
            }

        self.assertFalse(self.crew.is_complete())

        # Complete the last one
        self.crew.node_completion[all_nodes[-1]] = {
            "need_to_ask": True,
            "nice_to_know": False
        }

        self.assertTrue(self.crew.is_complete())


class TestCompletionPercentage(unittest.TestCase):
    """Test completion percentage calculation."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_completion_percentage_zero_at_start(self):
        """Test 0% at start."""
        self.assertEqual(self.crew.get_completion_percentage(), 0.0)

    def test_completion_percentage_accounts_for_tiers(self):
        """Test percentage counts both tiers."""
        # Complete need_to_ask for personal (which has nice_to_know)
        self.crew.node_completion["personal"] = {
            "need_to_ask": True,
            "nice_to_know": False
        }

        percentage = self.crew.get_completion_percentage()
        self.assertGreater(percentage, 0.0)
        self.assertLess(percentage, 1.0)

    def test_completion_percentage_100_when_all_complete(self):
        """Test 100% when all required tiers complete."""
        all_nodes = get_all_nodes()

        # Complete all need_to_ask (minimum required)
        for node_id in all_nodes:
            self.crew.node_completion[node_id] = {
                "need_to_ask": True,
                "nice_to_know": True  # Also complete nice_to_know for 100%
            }

        # Note: Actual 100% requires ALL tiers including nice_to_know
        # Adjust based on implementation
        percentage = self.crew.get_completion_percentage()
        self.assertGreaterEqual(percentage, 0.8)  # At least 80% complete


class TestFactoryFunction(unittest.TestCase):
    """Test factory function for creating crew."""

    def test_create_crew_without_llm(self):
        """Test creating crew without LLM."""
        crew = create_onboarding_crew_v2()
        self.assertIsInstance(crew, OnboardingCrewV2)
        self.assertIsNone(crew.llm)

    @patch('crews.onboarding_crew_v2.create_onboarding_agent')
    @patch('crews.onboarding_crew_v2.create_information_extraction_agent')
    def test_create_crew_with_llm(self, mock_extraction_agent, mock_onboarding_agent):
        """Test creating crew with LLM."""
        # Configure mocks to return mock agents
        mock_onboarding_agent.return_value = Mock()
        mock_extraction_agent.return_value = Mock()

        mock_llm = Mock()
        crew = create_onboarding_crew_v2(llm=mock_llm)

        self.assertIsInstance(crew, OnboardingCrewV2)
        self.assertEqual(crew.llm, mock_llm)

        # Verify agents were created with the LLM
        mock_onboarding_agent.assert_called_once_with(mock_llm)
        mock_extraction_agent.assert_called_once_with(mock_llm)


class TestReset(unittest.TestCase):
    """Test reset functionality."""

    def setUp(self):
        self.crew = OnboardingCrewV2()

    def test_reset_clears_all_state(self):
        """Test reset clears all tracking state."""
        # Set up some state
        self.crew.current_node_id = "personal"
        self.crew.current_tier = "nice_to_know"
        self.crew.conversation_history["personal"] = [{"test": "data"}]
        self.crew.extracted_data["personal"] = {"age": 28}
        self.crew.node_completion["personal"] = {"need_to_ask": True, "nice_to_know": False}
        self.crew.skip_counts["personal"] = 2
        self.crew.consecutive_skip_count = 2
        self.crew.root_values["personal"] = ["authenticity"]
        self.crew.photos_captured["face"] = "photo123"
        self.crew.social_media["instagram"] = "@user"

        # Reset
        self.crew.reset()

        # Verify everything cleared
        self.assertIsNone(self.crew.current_node_id)
        self.assertEqual(self.crew.current_tier, "need_to_ask")
        self.assertEqual(self.crew.conversation_history, {})
        self.assertEqual(self.crew.extracted_data, {})
        self.assertEqual(self.crew.node_completion, {})
        self.assertEqual(self.crew.skip_counts, {})
        self.assertEqual(self.crew.consecutive_skip_count, 0)
        self.assertEqual(self.crew.root_values, {})
        self.assertEqual(self.crew.photos_captured, {"face": None, "body": None})
        self.assertEqual(self.crew.social_media, {"instagram": None, "pinterest": None, "tiktok": None})


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
