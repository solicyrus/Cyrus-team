"""Support Agent proof on demo-dental:
grounded answers, honest refusal, lead capture."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_demo_client  # noqa: E402

from business_suite.agents import SupportAgent  # noqa: E402
from business_suite.llm import FakeLLM  # noqa: E402


class SupportAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = make_demo_client(self)
        # FakeLLM's default handler returns "" -> agents compose
        # deterministically from the knowledge passages themselves.
        self.agent = SupportAgent(self.client, llm=FakeLLM())

    def test_price_question_answered_verbatim_from_knowledge(self):
        result = self.agent.answer("How much does teeth whitening cost?")
        self.assertTrue(result.grounded)
        self.assertIn("$299", result.answer)  # exact figure from pricing.md
        self.assertTrue(any("pricing.md" in s for s in result.sources),
                        f"sources were: {result.sources}")

    def test_hours_question_answered_from_knowledge(self):
        result = self.agent.answer("When do you open on Saturdays?")
        self.assertTrue(result.grounded)
        self.assertIn("Saturday", result.answer)
        self.assertIn("2:00 pm", result.answer)

    def test_insurance_question_answered_from_knowledge(self):
        result = self.agent.answer("Do you bill insurance directly?")
        self.assertTrue(result.grounded)
        self.assertIn("direct-bill", result.answer)

    def test_out_of_knowledge_question_refused_honestly(self):
        result = self.agent.answer("Do you offer wedding catering for 200 guests?")
        self.assertFalse(result.grounded)
        self.assertEqual(result.sources, [])
        self.assertIn("don't have that information", result.answer)
        # The refusal routes to a human using the client's real contacts…
        self.assertIn("hello@brightsmile.example", result.answer)
        self.assertIn("BrightSmile Dental Studio", result.answer)
        # …and invents nothing: no prices anywhere in a refusal.
        self.assertNotIn("$", result.answer)

    def test_lead_captured_from_customer_message(self):
        result = self.agent.handle_message(
            "Hi, I'm Sara Mitchell (sara.mitchell@example.com). "
            "I'd like to know the price of teeth whitening, please.")
        self.assertTrue(result.grounded)          # question still answered
        self.assertIn("$299", result.answer)
        self.assertIsNotNone(result.lead)
        self.assertEqual(result.lead["contact"], "sara.mitchell@example.com")
        leads = self.agent.crm.list("leads")
        self.assertEqual(len(leads), 1)
        self.assertIn("whitening", leads[0]["need"])

    def test_direct_lead_capture_and_empty_lead_refused(self):
        record = self.agent.capture_lead(
            name="Omar Reyes", contact="+1-250-555-0199",
            need=" implant quote ")
        self.assertEqual(record["id"], "lead-0001")
        with self.assertRaises(ValueError):
            self.agent.capture_lead()  # no contact, no need -> refused

    def test_works_without_any_llm(self):
        agent = SupportAgent(self.client, llm=None)
        result = agent.answer("How much does teeth whitening cost?")
        self.assertTrue(result.grounded)
        self.assertEqual(result.mode, "deterministic")
        self.assertIn("$299", result.answer)


if __name__ == "__main__":
    unittest.main()
