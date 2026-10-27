"""CYRUS TEAM — main_pipeline.py

THE ORCHESTRATOR. One pipeline, four senior agents, each agent's
output is the next one's input:

    Strategist (Mastermind)   real signals -> grounded ideas
        -> Director           idea -> script package (+ optional
                              voice/render via the Developer)
        -> Strict QA gate     fact-scan + critic + media QA
        -> publish queue      QA-passed items ONLY, as
                              "awaiting_approval" — Cyrus approves
                              (standing rule: videos shown to him
                              first), then the Developer publishes
                              approved items and records the REAL
                              per-channel results.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smart_agents import common  # noqa: E402
from smart_agents import developer_agent, qa_agent  # noqa: E402
from smart_agents.director_agent import DirectorAgent  # noqa: E402
from smart_agents.queue import (APPROVED, AWAITING_APPROVAL,  # noqa: E402
                                AWAITING_QA, PARTIAL, PUBLISHED,
                                ApprovalQueue)
from smart_agents.strategist_agent import StrategistAgent  # noqa: E402

log = common.get_logger("pipeline")


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
        "ok" is True only when at least one item reached
        awaiting_approval. Every item carries its own true
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
                  == AWAITING_APPROVAL]
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
        """Mark a QA-passed entry approved (Cyrus's decision,
        recorded by the manager). Returns True/False."""
        entry, err = self.queue.find(entry_id)
        if err or entry.get("status") != AWAITING_APPROVAL:
            return False
        return self.queue.set_status(entry["id"], APPROVED)

    def publish_approved(self):
        """Publish every approved entry via the Developer and
        record the REAL results. Returns a list of outcomes."""
        outcomes = []
        for entry in self.queue.by_status(APPROVED):
            result = self.developer.publish(entry)
            new_status = PUBLISHED if result["all_ok"] else PARTIAL
            self.queue.set_status(
                entry["id"], new_status, results=result["results"],
                published_at=datetime.now().isoformat())
            outcomes.append({"id": entry["id"], "status": new_status,
                             "results": result["results"]})
            log.info("published %s -> %s", entry["id"], new_status)
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
              "not approved (unknown id or not awaiting_approval)")
        return 0 if ok else 1
    outcomes = pipeline.publish_approved()
    print(json.dumps(outcomes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
