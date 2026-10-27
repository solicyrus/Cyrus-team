"""CYRUS TEAM — main_pipeline.py

THE ORCHESTRATOR. One pipeline, four senior agents, each agent's
output is the next one's input:

    Strategist (Mastermind)   real signals -> grounded ideas
        -> Director           idea -> script package (+ optional
                              voice/render via the Developer)
        -> Strict QA gate     fact-scan + critic + media QA
        -> publish queue      QA-passed items ONLY, landing as
                              "draft" — the APPROVAL GATE holds
                              every draft until AUTO_PUBLISH is
                              exactly "True" in the environment or
                              a human manually approves the item
                              (standing rule: videos shown to Cyrus
                              first). Only then does the Developer
                              publish, recording the REAL per-channel
                              results.

A QA rejection stops the item: it lands in the queue as
"rejected" with qa_reasons recorded, and this pipeline never
promotes a rejected item. A stage that cannot run reports its
honest failure (stage + reason) — the run summary never dresses a
failure up as a package.

Usage (from the repo root):
    python main_pipeline.py run --topic "Vancouver Island travel"
    python main_pipeline.py run --topic "..." --with-video
    python main_pipeline.py status
    python main_pipeline.py approve <entry-id>
    python main_pipeline.py publish
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime

# Interpreter standard (VIRAL-PROTOCOL §7): pipeline runs use
# the robot-team venv python, which carries python-dotenv +
# openai. Run as a script under any other interpreter, this
# entry point re-execs itself under the venv python BEFORE the
# .env load — the old guarded load skipped .env SILENTLY and the
# team ran unconfigured while reporting nothing (2026-10-27 fix
# order). Imported use (tests) never triggers the re-exec.
if __name__ == "__main__":
    import venv_bootstrap

    venv_bootstrap.ensure_team_interpreter()

# Load the repo-root .env (if present) before anything reads the
# environment. Real values live ONLY in that local file — never in
# the repo. Guarded: when this module is IMPORTED (tests), the
# caller owns the environment; the script path above guarantees
# dotenv is importable before this point.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smart_agents import common  # noqa: E402
from smart_agents import developer_agent, qa_agent  # noqa: E402
from smart_agents.director_agent import DirectorAgent  # noqa: E402
from smart_agents.queue import (APPROVED, AWAITING_APPROVAL,  # noqa: E402
                                AWAITING_QA, DRAFT, PARTIAL,
                                PUBLISHED, ApprovalQueue)
from smart_agents.strategist_agent import StrategistAgent  # noqa: E402

log = common.get_logger("pipeline")

# Statuses that mean "QA passed, sitting in the publishing queue
# as a draft". DRAFT is the current label; AWAITING_APPROVAL is the
# legacy label from queues written before 2026-10-27. The approval
# gate treats them identically.
DRAFT_STATES = (DRAFT, AWAITING_APPROVAL)


def auto_publish_enabled():
    """The AUTO_PUBLISH gate flag: only the exact string "True"
    opens the gate. Unset, "False", or anything else keeps every
    draft held for manual approval."""
    return (os.environ.get("AUTO_PUBLISH") or "").strip() == "True"


class Pipeline:
    """strategist -> director -> qa -> publish queue."""

    def __init__(self, queue_path=None, workdir=None):
        self.queue = ApprovalQueue(queue_path)
        self.strategist = StrategistAgent(queue_path=queue_path)
        self.director = DirectorAgent()
        self.qa = qa_agent.QaAgent()
        self.developer = developer_agent.DeveloperAgent()
        self.workdir = workdir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "work")

    # -- one full run -------------------------------------------------
    def run(self, topics, n_ideas=3, niche="travel",
            target_seconds=30, with_video=False, dry_run=False):
        """Run the pipeline once. Returns a run report:
        {"ok": bool, "stage": ..., "items": [...], ...}.
        "ok" is True only when at least one item reached the
        publishing queue as a draft. Every item carries its own true
        outcome; failures name their stage and reason."""
        log.info("pipeline run: topics=%s with_video=%s dry_run=%s",
                 topics, with_video, dry_run)
        strategy = self.strategist.run(topics, n_ideas=n_ideas,
                                       niche=niche)
        if not strategy.get("ok"):
            return {"ok": False, "stage": strategy.get("stage"),
                    "error": strategy.get("error"),
                    "items": []}

        items = []
        for idea in strategy["ideas"]:
            items.append(self._process_idea(
                idea, target_seconds=target_seconds,
                with_video=with_video, dry_run=dry_run))
        passed = [i for i in items if i.get("status")
                  in DRAFT_STATES]
        return {"ok": len(passed) > 0, "stage": "done",
                "items": items,
                "signals": strategy.get("signals", []),
                "fetched_at": strategy.get("fetched_at")}

    def _process_idea(self, idea, target_seconds=30,
                      with_video=False, dry_run=False):
        """One idea through Director -> (render) -> QA -> queue."""
        built = self.director.build_package(
            idea, target_seconds=target_seconds)
        if not built.get("ok"):
            log.warning("director failed for idea %r: %s",
                        idea.get("title"), built.get("error"))
            return {"idea": idea, "status": "director_failed",
                    "stage": built.get("stage"),
                    "error": built.get("error")}
        package = built["package"]
        entry = {
            "id": uuid.uuid4().hex[:8],
            "idea": idea,
            "script": package["script"],
            "image_prompt": package.get("image_prompt"),
            "video_prompt": package.get("video_prompt"),
            "image": package.get("image"),
            "video_path": None,
            "channels": ["telegram"],
            "created_at": datetime.now().isoformat(),
            "status": AWAITING_QA,
        }
        self.queue.add(entry)

        if with_video and not dry_run:
            out_path = os.path.join(
                self.workdir, entry["id"], "video.mp4")
            rendered = self.developer.render_package_video(
                entry, out_path, target_seconds=target_seconds,
                workdir=os.path.join(self.workdir, entry["id"]))
            if rendered.get("ok"):
                self.queue.set_status(
                    entry["id"], AWAITING_QA,
                    video_path=entry["video_path"],
                    render=entry.get("render"),
                    voice=entry.get("voice"))
            else:
                # The video leg failed honestly; the text package
                # still goes to QA, with the failure recorded.
                self.queue.set_status(
                    entry["id"], AWAITING_QA,
                    video_error={"stage": rendered.get("stage"),
                                 "error": str(rendered.get("error"))})
                entry["video_error"] = rendered

        verdict = self.qa.check(entry, queue=self.queue)
        entry_now, _err = self.queue.find(entry["id"])
        return {"idea": idea, "id": entry["id"],
                "status": (entry_now or {}).get("status"),
                "qa_passed": verdict["passed"],
                "qa_reasons": verdict["reasons"],
                "qa_warnings": verdict["warnings"]}

    # -- human approval + publishing ----------------------------------
    def approve(self, entry_id):
        """Manual approval: flip a QA-passed draft to approved
        (Cyrus's decision, recorded by the manager). This marker
        is one of the only two ways the publishing gate opens.
        Returns True/False."""
        entry, err = self.queue.find(entry_id)
        if err or entry.get("status") not in DRAFT_STATES:
            return False
        return self.queue.set_status(
            entry["id"], APPROVED, approved_by="manual",
            approved_at=datetime.now().isoformat())

    def publish_approved(self):
        """THE APPROVAL GATE. An entry is sent ONLY when:

          * it carries the manual approval marker (status
            "approved" — see approve()), OR
          * AUTO_PUBLISH is exactly "True" in the environment and
            the entry is a QA-passed draft.

        Every other draft is HELD: nothing is sent, the hold is
        logged, and the entry stays a draft. Returns the list of
        outcomes for entries actually published (empty when the
        gate held everything)."""
        outcomes = []
        auto = auto_publish_enabled()
        candidates = list(self.queue.by_status(APPROVED))
        for entry in self.queue.all():
            if entry.get("status") in DRAFT_STATES:
                if auto:
                    candidates.append(entry)
                else:
                    log.info(
                        "approval gate: HOLD draft %s — AUTO_PUBLISH "
                        "is not \"True\" and the item has no manual "
                        "approval; nothing sent", entry.get("id"))
        for entry in candidates:
            basis = ("manual approval"
                     if entry.get("status") == APPROVED
                     else "AUTO_PUBLISH=True")
            result = self.developer.publish(entry)
            new_status = PUBLISHED if result["all_ok"] else PARTIAL
            self.queue.set_status(
                entry["id"], new_status, results=result["results"],
                published_at=datetime.now().isoformat())
            outcomes.append({"id": entry["id"], "status": new_status,
                             "results": result["results"]})
            log.info("approval gate: PUBLISH %s (%s) -> %s",
                     entry["id"], basis, new_status)
        return outcomes

    def status(self):
        counts = {}
        for entry in self.queue.all():
            s = entry.get("status", "?")
            counts[s] = counts.get(s, 0) + 1
        return {"queue": counts, "total": len(self.queue.all())}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cyrus Team pipeline — strategist -> director "
                    "-> QA -> publish queue")
    parser.add_argument("--queue", default=None,
                        help="approval queue path (default: repo "
                             "root approval_queue.json)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--topic", action="append", required=True,
                       help="topic (repeatable)")
    p_run.add_argument("--ideas", type=int, default=3)
    p_run.add_argument("--seconds", type=int, default=30)
    p_run.add_argument("--with-video", action="store_true")
    p_run.add_argument("--dry-run", action="store_true",
                       help="build + QA only; never render/publish")
    sub.add_parser("status")
    p_app = sub.add_parser("approve")
    p_app.add_argument("entry_id")
    sub.add_parser("publish")
    args = parser.parse_args(argv)

    pipeline = Pipeline(queue_path=args.queue)
    if args.cmd == "run":
        result = pipeline.run(args.topic, n_ideas=args.ideas,
                              target_seconds=args.seconds,
                              with_video=args.with_video,
                              dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if args.cmd == "status":
        print(json.dumps(pipeline.status(), indent=2))
        return 0
    if args.cmd == "approve":
        ok = pipeline.approve(args.entry_id)
        print("approved" if ok else
              "not approved (unknown id or not a QA-passed draft)")
        return 0 if ok else 1
    outcomes = pipeline.publish_approved()
    print(json.dumps(outcomes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
