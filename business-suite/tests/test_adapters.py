"""Adapter honesty proof: unconfigured integrations must SAY so.
A stub that fakes success is a defect — these tests pin that down."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (import path bootstrap)

from business_suite.adapters import NotConfiguredError  # noqa: E402
from business_suite.adapters.external_crm import ExternalCRMAdapter  # noqa: E402
from business_suite.adapters.instagram import InstagramAdapter  # noqa: E402
from business_suite.adapters.whatsapp import WhatsAppAdapter  # noqa: E402


class AdapterHonestyTests(unittest.TestCase):
    def test_whatsapp_reports_not_configured_and_refuses_send(self):
        adapter = WhatsAppAdapter("demo-dental")
        status = adapter.status()
        self.assertFalse(status["configured"])
        self.assertIn("WHATSAPP", status["reason"])
        with self.assertRaises(NotConfiguredError):
            adapter.send_message("+1-250-555-0100", "hello")

    def test_instagram_reports_not_configured_and_refuses_send(self):
        adapter = InstagramAdapter("demo-dental")
        self.assertFalse(adapter.status()["configured"])
        with self.assertRaises(NotConfiguredError):
            adapter.send_message("@someone", "hello")

    def test_external_crm_refuses_push(self):
        adapter = ExternalCRMAdapter("demo-dental")
        self.assertFalse(adapter.status()["configured"])
        with self.assertRaises(NotConfiguredError):
            adapter.push_record("leads", {"name": "Test"})


if __name__ == "__main__":
    unittest.main()
