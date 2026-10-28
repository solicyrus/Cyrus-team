#!/usr/bin/env python3
"""Business Suite — one-command demo on the demo-dental client.

Runs all three agents against a THROWAWAY COPY of the demo client
(CRM writes and reports never touch the shipped fixture) and prints
what each agent produced, including the honest labels (grounded or
refused, llm or deterministic).

Usage:
    python3 run_demo.py [--llm]

Without --llm everything runs deterministically (no key, no network).
With --llm, the agents use the real LLM wrapper if OPENAI_API_KEY is
available (repo .env counts); if it is not, the demo says so and
falls back instead of pretending.
"""

import argparse
import os
import shutil
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from business_suite.agents import ContentAgent, SupportAgent, WorkflowAgent
from business_suite.config import load_client
from business_suite.llm import FakeLLM, get_llm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true",
                        help="use the real LLM if a key is configured")
    args = parser.parse_args()

    if args.llm:
        llm = get_llm()
        mode = "real LLM" if llm is not None else \
            "deterministic (no OPENAI_API_KEY found — NOT using an LLM)"
    else:
        llm = FakeLLM()
        mode = "FakeLLM (offline demo — deterministic outputs)"

    tmp = tempfile.mkdtemp(prefix="bs-run-")
    try:
        shutil.copytree(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "clients", "demo-dental"),
            os.path.join(tmp, "demo-dental"))
        client = load_client("demo-dental", clients_dir=tmp)
        cfg = client.config
        print(f"=== Business Suite demo — {cfg.business_name} ({cfg.niche})")
        print(f"=== Mode: {mode}\n")

        support = SupportAgent(client, llm=llm)
        for question in (
            "How much does teeth whitening cost?",
            "Do you offer wedding catering for 200 guests?",
        ):
            result = support.answer(question)
            print(f"[Support] Q: {question}")
            print(f"[Support] grounded={result.grounded} mode={result.mode} "
                  f"sources={result.sources}")
            print(f"[Support] A: {result.answer.splitlines()[0]}...\n")
        lead = support.handle_message(
            "Hi, I'm Sara Mitchell (sara.mitchell@example.com). "
            "I'd like to know the price of teeth whitening, please.")
        print(f"[Support] Lead captured: {lead.lead}\n")

        content = ContentAgent(client, llm=llm)
        signals = content.trend_scan()
        print(f"[Content] Trend signals: {len(signals)} "
              f"(sources: {sorted({s.source for s in signals})})")
        calendar = content.build_calendar(start=date(2026, 11, 2), days=7)
        for item in calendar:
            print(f"[Content] Day {item.day} {item.date} — {item.pillar} / "
                  f"{item.format} — hook: {item.hook}")
        script = content.write_script(calendar[0])
        print(f"[Content] Script for day 1: {len(script.scenes)} scenes, "
              f"{script.duration_s}s, generated_with={script.generated_with}\n")

        workflow = WorkflowAgent(client, llm=llm)
        report = workflow.process_inbox(today=date(2026, 10, 27))
        print(f"[Workflow] Processed {report.total} messages -> {report.counts}")
        print(f"[Workflow] Needs human action: {len(report.needs_action)} items")
        print(f"[Workflow] Report written to: {report.report_path}")
        print(f"[Workflow] CRM counts now: {workflow.crm.counts()}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
