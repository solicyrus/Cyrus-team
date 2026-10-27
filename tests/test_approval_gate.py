#!/usr/bin/env python3
"""CYRUS TEAM — tests/test_approval_gate.py

PROOF for the approval gate (Cyrus's activation Protocol 2):

  * QA-passed packages sit in the publishing queue as DRAFTS.
  * A draft is sent ONLY when AUTO_PUBLISH is exactly "True" in
    the environment OR the item carries a manual approval.
  * With the gate closed, publish_approved() returns [] and the
    send path is NEVER entered — even when (dummy) Telegram
    credentials are present in the environment.

The Developer's Telegram transport is replaced with a counting
fake, so this test can never send anything real. The fake stands
exactly where the real send would happen: if the gate let an
item through, the fake records the call and the pipeline marks
the item published — that is the "gate opened" evidence.

Run:  python3 tests/test_approval_gate.py   (exit 0 = all pass)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# Deterministic environment: gate closed, but Telegram FULLY
# (dummy-)configured — the gate, not missing credentials, must
# be what stops the send.
os.environ.pop("AUTO_PUBLISH", None)
os.environ["TELEGRAM_BOT_TOKEN"] = "dummy-token-for-gate-test"
os.environ["TELEGRAM_CHAT_ID"] = "123456789"

from main_pipeline import Pipeline, auto_publish_enabled  # noqa: E402
from smart_agents import developer_agent  # noqa: E402
from smart_agents.queue import DRAFT, PUBLISHED  # noqa: E402

CALLS = []


def _fake_send(*args, **kwargs):
    CALLS.append((args, kwargs))
    return {"ok": True, "fake_transport": True,
            "detail": "counted by the gate test; nothing was sent"}


developer_agent.telegram_publish = _fake_send
developer_agent.telegram_publish_file = _fake_send
developer_agent.instagram_publish = _fake_send
developer_agent.instagram_publish_reel = _fake_send
developer_agent.youtube_upload = _fake_send

FAILURES = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} — {name}"
          + (f" ({detail})" if detail else ""))
    if not condition:
        FAILURES.append(name)


def make_draft(pipe, entry_id):
    pipe.queue.add({
        "id": entry_id,
        "idea": {"title": "gate test"},
        "script": {"caption": "gate test caption",
                   "title": "gate test"},
        "channels": ["telegram"],
        "video_path": None,
        "status": DRAFT,
    })
    return entry_id


def status_of(pipe, entry_id):
    entry, _err = pipe.queue.find(entry_id)
    return (entry or {}).get("status")


def main():
    tmp = tempfile.mkdtemp(prefix="cyrus-gate-test-")
    pipe = Pipeline(queue_path=os.path.join(tmp, "queue.json"))

    check("flag semantics: unset AUTO_PUBLISH keeps gate closed",
          auto_publish_enabled() is False)

    # Case A — gate closed, one draft, dummy creds present.
    make_draft(pipe, "gate-a")
    outcomes = pipe.publish_approved()
    check("A: closed gate publishes nothing", outcomes == [],
          f"outcomes={outcomes}")
    check("A: send path never entered", CALLS == [],
          f"transport calls={len(CALLS)}")
    check("A: item remains a draft",
          status_of(pipe, "gate-a") == DRAFT)

    # Case B — manual approval opens the gate for that item only.
    check("B: manual approve() accepts the draft",
          pipe.approve("gate-a") is True)
    outcomes = pipe.publish_approved()
    check("B: approved item is published", len(outcomes) == 1
          and outcomes[0]["id"] == "gate-a",
          f"outcomes={outcomes}")
    check("B: send path reached exactly once", len(CALLS) == 1,
          f"transport calls={len(CALLS)}")
    check("B: item now marked published",
          status_of(pipe, "gate-a") == PUBLISHED)
    entry, _ = pipe.queue.find("gate-a")
    check("B: manual approval marker recorded",
          entry.get("approved_by") == "manual")

    # Case C — AUTO_PUBLISH=True opens the gate for drafts.
    make_draft(pipe, "gate-c")
    os.environ["AUTO_PUBLISH"] = "True"
    check("flag semantics: exactly 'True' opens the gate",
          auto_publish_enabled() is True)
    outcomes = pipe.publish_approved()
    check("C: draft published under AUTO_PUBLISH=True",
          len(outcomes) == 1 and outcomes[0]["id"] == "gate-c",
          f"outcomes={outcomes}")
    check("C: send path reached", len(CALLS) == 2,
          f"transport calls={len(CALLS)}")

    # Case D — AUTO_PUBLISH=false (lowercase) does NOT open it.
    make_draft(pipe, "gate-d")
    os.environ["AUTO_PUBLISH"] = "false"
    check("flag semantics: 'false' keeps the gate closed",
          auto_publish_enabled() is False)
    outcomes = pipe.publish_approved()
    check("D: nothing published", outcomes == [])
    check("D: send path not entered again", len(CALLS) == 2,
          f"transport calls={len(CALLS)}")
    check("D: item remains a draft",
          status_of(pipe, "gate-d") == DRAFT)

    print("-" * 60)
    if FAILURES:
        print(f"GATE TEST: FAILED — {len(FAILURES)} check(s): "
              + ", ".join(FAILURES))
        return 1
    print("GATE TEST: ALL CHECKS PASSED — drafts are held unless "
          "AUTO_PUBLISH=True or a human approved the item.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
