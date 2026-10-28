"""Workflow Agent proof on demo-dental:
the 9-message sample inbox is classified, records land in the CRM
store, and the daily summary report is written."""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_demo_client  # noqa: E402

from business_suite.agents import WorkflowAgent  # noqa: E402
from business_suite.llm import FakeLLM  # noqa: E402

TODAY = date(2026, 10, 27)


class WorkflowAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = make_demo_client(self)
        self.agent = WorkflowAgent(self.client, llm=FakeLLM())
        self.report = self.agent.process_inbox(today=TODAY)

    def test_inbox_counts_match_fixture(self):
        self.assertEqual(self.report.total, 9)
        self.assertEqual(self.report.counts, {
            "order": 1, "appointment": 3, "question": 3,
            "spam": 2, "needs_review": 0,
        })

    def test_ambiguous_message_used_llm_fallback(self):
        item = next(i for i in self.report.items
                    if i.filename.startswith("09-"))
        self.assertEqual(item.category, "question")
        self.assertEqual(item.method, "llm-fallback")

    def test_order_record_created_with_extracted_fields(self):
        orders = self.agent.crm.list("orders")
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order["contact"], "tom.becker@example.com")
        self.assertIn("whitening", order["item"])
        self.assertIn("kit", order["item"])
        self.assertEqual(order["quantity"], 2)
        self.assertEqual(order["status"], "new")

    def test_appointment_records_created_with_fields(self):
        appts = self.agent.crm.list("appointments")
        self.assertEqual(len(appts), 3)
        by_customer = {a["customer"]: a for a in appts}
        maria = by_customer["Maria Chen"]
        self.assertEqual(maria["service"], "Dental cleaning and checkup")
        self.assertIn("November 3", maria["date_text"])
        self.assertIn("10:30", maria["time_text"])
        james = by_customer["James O'Neil"]
        self.assertEqual(james["service"], "Invisalign consultation")
        priya = by_customer["Priya Nair"]
        self.assertIn("November 6", priya["date_text"])

    def test_summary_report_written_with_action_list(self):
        self.assertTrue(self.report.report_path)
        self.assertTrue(os.path.isfile(self.report.report_path))
        with open(self.report.report_path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Orders: 1", text)
        self.assertIn("Appointments: 3", text)
        self.assertIn("Needs human action", text)
        self.assertIn("sara.lee@example.com", text)       # insurance question
        self.assertIn("ruth.alvarez@example.com", text)   # fallback question
        self.assertEqual(len(self.report.needs_action), 3)

    def test_without_llm_ambiguous_goes_to_needs_review(self):
        client2 = make_demo_client(self)
        agent2 = WorkflowAgent(client2, llm=None)
        report2 = agent2.process_inbox(today=TODAY, write_report=False)
        self.assertEqual(report2.counts["needs_review"], 1)
        self.assertEqual(report2.counts["question"], 2)
        stuck = next(i for i in report2.items if i.filename.startswith("09-"))
        self.assertEqual(stuck.category, "needs_review")
        self.assertEqual(stuck.method, "unresolved")


if __name__ == "__main__":
    unittest.main()
