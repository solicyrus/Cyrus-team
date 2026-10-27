"""CYRUS TEAM — smart_agents/qa_agent.py

🛡️ THE STRICT QA (Senior) — the final guard before anything can
reach Cyrus or a publish queue.

Charter job: check video quality, captions, hashtags and package
structure BEFORE finalising — and reject ruthlessly. A package
that fails is moved to the REJECTED state with its reasons
recorded, and the pipeline can never promote it to the publish
queue. (This restores the power the old factory's quality
gatekeeper was deliberately denied in 2026-10-25; Cyrus's rebuild
charter of 2026-10-27 orders it back.)

Three layers, in order:
1. TEXT QA — the deterministic fact-scan (smart_agents/facts.py:
   invented prices / hours / phone numbers — HARD FAIL, the only
   text authority) + structural sanity: a missing hook, title or
   caption is a hard fail; hashtag count and caption length are
   warnings. The AI fact layer adds warnings only.
2. CRITIC — a thinking-tier hook/quality score. Per the charter it
   CAN reject — but only when it actually ran (ai_used) and scores
   a package below 4/10 with a stated reason. When the AI is
   unavailable the critic abstains; it never fabricates a verdict.
3. MEDIA QA — ffprobe on the rendered video: existence, video
   stream, duration, resolution (vertical 9:16 at >= 720 wide),
   audio-stream presence. A video that fails is rejected on
   measured facts, not opinions. (The old team had NOTHING that
   inspected a finished render — audit diagnosis #6.)

Two-state rule: a package is either verified PASS, or REJECTED
with reasons. There is no third, pretend state.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from smart_agents import common  # noqa: E402
from smart_agents import facts  # noqa: E402
from smart_agents.queue import DRAFT, REJECTED  # noqa: E402

log = common.get_logger("qa")

TEXT_FIELDS = ("hook", "title", "caption", "description", "script")
MAX_HASHTAGS = 15
MAX_CAPTION_CHARS = 2200
CRITIC_REJECT_BELOW = 4.0

MIN_VIDEO_WIDTH = 720
MIN_VIDEO_HEIGHT = 1280


# ==================================================================
# 1. TEXT QA
# ==================================================================

def check_texts(script):
    """Text QA over a script dict {hook, title, caption,
    description, script, hashtags}.

    Returns {"passed": bool, "flags": [...], "warnings": [...],
    "fact_check": {...}}. Hard flags: fact-scan hits + missing
    hook/title/caption.
    """
    script = script or {}
    texts = {f: str(script.get(f, "") or "") for f in TEXT_FIELDS}
    flags = []
    warnings = []

    for field in ("hook", "title", "caption"):
        if not texts[field].strip():
            flags.append(f"missing required field: {field}")

    fact_result = facts.check_facts(texts)
    flags.extend(fact_result["flags"])
    warnings.extend(fact_result["warnings"])

    hashtags = script.get("hashtags") or []
    if len(hashtags) > MAX_HASHTAGS:
        warnings.append(
            f"hashtag count {len(hashtags)} exceeds {MAX_HASHTAGS}")
    if len(texts["caption"]) > MAX_CAPTION_CHARS:
        warnings.append(
            f"caption is {len(texts['caption'])} chars "
            f"(> {MAX_CAPTION_CHARS})")

    return {"passed": len(flags) == 0, "flags": flags,
            "warnings": warnings, "fact_check": fact_result}


# ==================================================================
# 2. CRITIC — quality score with charter rejection power
# ==================================================================

_CRITIC_SYSTEM = (
    "You are THE STRICT QA of an AI travel content team — a "
    "ruthless senior critic. You score short-video packages for "
    "hook strength (first 2 seconds), clarity, and whether the "
    "ending lands one clear decision. You are stingy with points: "
    "average work is 5/10. Reply with ONLY valid JSON."
)


def critic_score(script):
    """Score a script package 0-10 with the thinking tier.

    Returns {"ai_used": bool, "score": float|None,
             "reason": str}. ai_used=False means the critic
    abstained (AI unavailable) — no verdict was fabricated.
    """
    script = script or {}
    joined = "\n".join(
        f"{f}: {script.get(f, '')}" for f in TEXT_FIELDS
        if str(script.get(f, "")).strip())
    if not joined:
        return {"ai_used": False, "score": None,
                "reason": "empty package — nothing to score"}
    prompt = (
        "Score this video package.\n" + joined[:2500] + "\n"
        'Reply ONLY valid JSON: {"score": <0-10 number>, '
        '"reason": "one sentence"}'
    )
    data, ok = common.ask_json(prompt, _CRITIC_SYSTEM,
                               role="thinking",
                               max_tokens=300, temperature=0.2)
    if not ok or not data or "score" not in data:
        return {"ai_used": False, "score": None,
                "reason": "critic unavailable — abstained"}
    try:
        score = float(data["score"])
    except (TypeError, ValueError):
        return {"ai_used": False, "score": None,
                "reason": "critic returned an unusable score — "
                          "abstained"}
    return {"ai_used": True, "score": score,
            "reason": str(data.get("reason", "")).strip()}


# ==================================================================
# 3. MEDIA QA — ffprobe technical gate
# ==================================================================

def probe_video(path):
    """ffprobe facts about a video file:
    {"exists", "readable", "duration_s", "width", "height",
     "has_audio", "has_video", "error"}."""
    facts_out = {"exists": os.path.isfile(path or ""),
                 "readable": False, "duration_s": None,
                 "width": None, "height": None,
                 "has_audio": False, "has_video": False,
                 "error": None}
    if not facts_out["exists"]:
        facts_out["error"] = f"file not found: {path}"
        return facts_out
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, timeout=30)
        if proc.returncode != 0:
            facts_out["error"] = (
                "ffprobe failed: "
                + proc.stderr.decode("utf-8", "replace")[:200])
            return facts_out
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except FileNotFoundError:
        facts_out["error"] = "ffprobe not found on this system"
        return facts_out
    except Exception as e:
        facts_out["error"] = f"{type(e).__name__}: {e}"
        return facts_out
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            facts_out["has_video"] = True
            facts_out["width"] = stream.get("width")
            facts_out["height"] = stream.get("height")
        elif stream.get("codec_type") == "audio":
            facts_out["has_audio"] = True
    try:
        facts_out["duration_s"] = round(
            float(data.get("format", {}).get("duration", 0)), 3)
    except (TypeError, ValueError):
        facts_out["duration_s"] = None
    facts_out["readable"] = facts_out["has_video"]
    return facts_out


def check_video(path, min_duration_s=None, expect_audio=True,
                min_width=MIN_VIDEO_WIDTH, min_height=MIN_VIDEO_HEIGHT):
    """Technical gate over a rendered video. Returns
    {"passed": bool, "flags": [...], "facts": {...}} — every flag
    is a measured fact from ffprobe."""
    facts_out = probe_video(path)
    flags = []
    if not facts_out["exists"]:
        flags.append(f"video file missing: {path}")
        return {"passed": False, "flags": flags, "facts": facts_out}
    if not facts_out["readable"]:
        flags.append("video is unreadable/corrupt or has no video "
                     f"stream ({facts_out['error']})")
        return {"passed": False, "flags": flags, "facts": facts_out}
    duration = facts_out["duration_s"]
    if duration is None or duration <= 0:
        flags.append("video has no measurable duration")
    elif min_duration_s is not None and duration < min_duration_s:
        flags.append(
            f"video too short: {duration}s < {min_duration_s}s")
    width = facts_out["width"] or 0
    height = facts_out["height"] or 0
    if width < min_width or height < min_height:
        flags.append(
            f"resolution too low: {width}x{height} "
            f"(< {min_width}x{min_height})")
    if width >= height:
        flags.append(
            f"not vertical: {width}x{height} (Shorts need 9:16)")
    if expect_audio and not facts_out["has_audio"]:
        flags.append("no audio stream — a published video must "
                     "carry its voice/music")
    return {"passed": len(flags) == 0, "flags": flags,
            "facts": facts_out}


# ==================================================================
# THE GATE — the only road to the publish queue
# ==================================================================

def check_package(package, queue=None):
    """Run the full QA gate over a package dict:
    {script: {...}, video_path: optional, id: queue id}.

    Verdict: {"passed": bool, "reasons": [...], "warnings": [...],
              "text_qa": ..., "critic": ..., "media_qa": ...}.

    When `queue` is given and the package has an "id", the verdict
    is APPLIED: pass -> status draft (publishing queue, held by
    the approval gate); fail -> status
    rejected with qa_reasons recorded. A rejected package can
    never be promoted by the pipeline from that state.
    """
    package = package or {}
    script = package.get("script") or {}
    reasons = []
    warnings = []

    text_qa = check_texts(script)
    reasons.extend(text_qa["flags"])
    warnings.extend(text_qa["warnings"])

    critic = critic_score(script)
    if critic["ai_used"] and critic["score"] is not None:
        if critic["score"] < CRITIC_REJECT_BELOW:
            reasons.append(
                f"critic rejected the package: "
                f"{critic['score']}/10 — {critic['reason']}")
        else:
            warnings.append(
                f"critic score: {critic['score']}/10 — "
                f"{critic['reason']}")
    else:
        warnings.append(f"critic abstained: {critic['reason']}")

    media_qa = None
    if package.get("video_path"):
        media_qa = check_video(package["video_path"])
        reasons.extend(media_qa["flags"])

    passed = len(reasons) == 0
    verdict = {"passed": passed, "reasons": reasons,
               "warnings": warnings, "text_qa": text_qa,
               "critic": critic, "media_qa": media_qa}

    if queue is not None and package.get("id"):
        if passed:
            queue.set_status(package["id"], DRAFT,
                             qa_verdict=_verdict_summary(verdict))
            log.info("QA PASS: %s -> draft (publishing queue, "
                     "approval gate holds it)",
                     package["id"])
        else:
            queue.set_status(package["id"], REJECTED,
                             qa_reasons=reasons,
                             qa_verdict=_verdict_summary(verdict))
            log.warning("QA REJECT: %s — %s",
                        package["id"], "; ".join(reasons))
    return verdict


def _verdict_summary(verdict):
    """Compact, JSON-safe summary stored on the queue entry."""
    critic = verdict.get("critic") or {}
    media = verdict.get("media_qa") or {}
    media_facts = media.get("facts") if media else None
    return {
        "passed": verdict["passed"],
        "reasons": verdict["reasons"],
        "warnings": verdict["warnings"],
        "critic_score": critic.get("score"),
        "media_facts": media_facts,
    }


class QaAgent:
    """The Strict QA as one callable agent."""

    def check(self, package, queue=None):
        return check_package(package, queue=queue)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The Strict QA — check a package JSON file")
    parser.add_argument("package_json",
                        help="path to a JSON package "
                             "({script: {...}, video_path: ...})")
    args = parser.parse_args(argv)
    with open(args.package_json, "r", encoding="utf-8") as f:
        package = json.load(f)
    verdict = check_package(package)
    print(json.dumps(_verdict_summary(verdict),
                     ensure_ascii=False, indent=2))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
