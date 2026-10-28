"""Content Agent proof on demo-dental:
labelled trend scan, a complete 7-day calendar, structured scripts."""

import json
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import make_demo_client  # noqa: E402

from business_suite.agents import ContentAgent  # noqa: E402
from business_suite.llm import FakeLLM  # noqa: E402


class ContentAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = make_demo_client(self)
        self.agent = ContentAgent(self.client, llm=FakeLLM())

    def test_trend_scan_labels_every_source(self):
        signals = self.agent.trend_scan()
        self.assertGreaterEqual(len(signals), 3)
        sources = {s.source for s in signals}
        self.assertIn("client-seed", sources)
        self.assertTrue(sources <= {"client-seed", "service-catalogue", "llm"})
        self.assertTrue(all(s.topic.strip() for s in signals))

    def test_seven_day_calendar_is_complete(self):
        start = date(2026, 11, 2)
        items = self.agent.build_calendar(start=start, days=7)
        self.assertEqual(len(items), 7)
        for i, item in enumerate(items):
            self.assertEqual(item.date, (start + timedelta(days=i)).isoformat())
            self.assertTrue(item.pillar.strip())
            self.assertTrue(item.format.strip())
            self.assertTrue(item.topic.strip())
            self.assertTrue(item.hook.strip())
            self.assertTrue(item.caption.strip())
            self.assertGreaterEqual(len(item.hashtags), 5,
                                    f"day {item.day} hashtags: {item.hashtags}")
            self.assertIn("#BrightSmile", item.hashtags)
        # The week rotates through ALL of the client's pillars…
        self.assertEqual({i.pillar for i in items},
                         set(self.client.config.content_pillars))
        # …and is video-heavy, as short-form strategy requires.
        videos = [i for i in items if "Short video" in i.format]
        self.assertGreaterEqual(len(videos), 3)

    def test_script_structure_from_calendar_item(self):
        item = self.agent.build_calendar(start=date(2026, 11, 2), days=7)[0]
        script = self.agent.write_script(item)
        self.assertEqual(script.hook, item.hook)          # hook-first, always
        self.assertGreaterEqual(len(script.scenes), 3)
        self.assertTrue(all(s["spoken"].strip() for s in script.scenes))
        self.assertEqual(script.duration_s, 30)
        self.assertTrue(script.cta.strip())
        self.assertIn("dentistry", script.caption)        # the demo niche
        self.assertEqual(script.generated_with, "deterministic")

    def test_script_uses_llm_when_it_returns_valid_json(self):
        payload = {
            "hook": "LLM hook: the whitening question everyone asks.",
            "scenes": [{"seconds": "0-5", "visual": "Reception close-up",
                        "spoken": "LLM hook: the whitening question everyone asks."},
                       {"seconds": "5-20", "visual": "Chair side",
                        "spoken": "Here is the honest answer."},
                       {"seconds": "20-30", "visual": "End card",
                        "spoken": "Message us to book."}],
            "cta": "Message us to book",
            "caption": "LLM caption for BrightSmile.",
        }

        def handler(system, user):
            if "short-video script" in user:
                return json.dumps(payload)
            return ""

        agent = ContentAgent(self.client, llm=FakeLLM(handler))
        item = agent.build_calendar(start=date(2026, 11, 2), days=7)[0]
        script = agent.write_script(item)
        self.assertEqual(script.generated_with, "llm")
        self.assertEqual(script.hook, payload["hook"])
        self.assertEqual(len(script.scenes), 3)


if __name__ == "__main__":
    unittest.main()
