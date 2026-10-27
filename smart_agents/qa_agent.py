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
2b. VIRAL CHECKLIST — the Viral Protocol's 4 questions
   (VIRAL-PROTOCOL.md §4: hook strength, pacing to 30s, prompt
   quality, loop integrity), answered literally with pass/fail +
   reason on every review. A failed question rejects when the
   judge ran; when it cannot run, it abstains like the critic.
3. MEDIA QA — ffprobe on the rendered video: existence, video
   stream, duration, resolution (vertical 9:16 at >= 720 wide),
   audio-stream presence — AND a hard DURATION GATE: a finished
   video longer than 31s FAILS the package. The Viral
   Protocol's 30s formula is a hard standard, not a target (fix
   order 2026-10-27, after draft a4f904cd rendered 34.5s and
   passed the old gate, which had no ceiling). A video that
   fails is rejected on measured facts, not opinions. (The old
   team had NOTHING that inspected a finished render — audit
   diagnosis #6.)

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

# DURATION GATE (VIRAL-PROTOCOL §2/§4): the golden formula is
# 30s. A finished video longer than this ceiling FAILS the
# package — measured by ffprobe, recorded on the verdict.
MAX_VIDEO_DURATION_S = 31.0


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
# 2b. VIRAL CHECKLIST — the Protocol's 4 questions (VIRAL-PROTOCOL §4)
#
# Asked LITERALLY on every review, answered pass/fail + reason by
# the thinking tier. A failed question rejects the package when
# the judge actually ran — the protocol's Strict QA Gate. When
# the AI is unavailable the checklist ABSTAINS (ai_used=False,
# passed=None) and never fabricates an answer.
# ==================================================================

VIRAL_QUESTIONS = (
    "Hook strength — does the first-3-seconds hook have "
    "multi-million-view stopping power (a real pattern interrupt "
    "plus a clear promise in the opening line)?",
    "Pacing — do story and rhythm hold all the way to second "
    "30: no filler, tension maintained through 3-15s, and the "
    "payoff landing at 15-25s?",
    "Prompt quality — are the visual prompts genuinely "
    "cinematic (camera, lighting, lens, texture specified) and "
    "free of cheap/artificial effects, with negative prompts "
    "guarding against them?",
    "Loop integrity — does the narrative loop actually work: "
    "does the final line of the script connect back into the "
    "opening hook line so an auto-replay feels seamless?",
)

_VIRAL_SYSTEM = (
    "You are THE STRICT QA of an AI travel content team, running "
    "the VIRAL PROTOCOL checklist. You judge a short-video "
    "package against four exact questions and answer each with "
    "pass (true/false) and ONE concrete reason. You are ruthless "
    "and specific: a vague hook, filler, a missing payoff, "
    "generic prompts, or a final line that does not re-enter "
    "the hook all FAIL. Average work fails. Reply with ONLY "
    "valid JSON."
)


def viral_checklist(script, video_prompt=None):
    """Answer the Protocol's 4 questions for one package.

    Returns {"ai_used": bool, "passed": bool|None,
             "answers": [{"question", "pass", "reason"}]}.
    passed is None (and answers empty) when the judge abstained
    — no verdict was fabricated.
    """
    script = script or {}
    beats = script.get("beats") or {}
    scenes = (video_prompt or {}).get("scenes") or []
    scene_lines = []
    for s in scenes:
        if isinstance(s, dict):
            scene_lines.append(
                f"shot {s.get('scene')}: "
                f"{str(s.get('prompt', ''))[:200]} | camera: "
                f"{s.get('camera', '')} | negatives: "
                f"{str(s.get('negative_prompt', ''))[:120]}")
    package_text = "\n".join([
        f"hook: {script.get('hook', '')}",
        f"title: {script.get('title', '')}",
        "beats: " + "; ".join(
            f"{k} = {beats[k]}" for k in beats if beats.get(k)),
        f"full script: {script.get('script', '')}",
        "video prompts:\n" + ("\n".join(scene_lines)
                               or "(none provided)"),
        f"global negative prompt: "
        f"{(video_prompt or {}).get('negative_prompt', '')}",
    ])
    questions_block = "\n".join(
        f"Q{i + 1}. {q}" for i, q in enumerate(VIRAL_QUESTIONS))
    prompt = (
        "Judge this video package against the four Viral "
        "Protocol questions.\n\n" + package_text[:3500] + "\n\n"
        + questions_block + "\n\n"
        'Reply ONLY valid JSON: {"answers": [{"q": 1, '
        '"pass": true, "reason": "one concrete sentence"}, '
        '... exactly 4 answers, q = 1..4]}'
    )
    data, ok = common.ask_json(prompt, _VIRAL_SYSTEM,
                               role="thinking",
                               max_tokens=700, temperature=0.2)
    if not ok or not data or not isinstance(data.get("answers"),
                                            list):
        return {"ai_used": False, "passed": None, "answers": [],
                "note": "viral checklist judge unavailable — "
                        "abstained"}
    by_q = {}
    for raw in data["answers"]:
        if not isinstance(raw, dict):
            continue
        try:
            qn = int(raw.get("q"))
        except (TypeError, ValueError):
            continue
        if 1 <= qn <= len(VIRAL_QUESTIONS):
            by_q[qn] = {
                "question": VIRAL_QUESTIONS[qn - 1],
                "pass": bool(raw.get("pass")),
                "reason": str(raw.get("reason", "")).strip(),
            }
    if len(by_q) != len(VIRAL_QUESTIONS):
        return {"ai_used": False, "passed": None, "answers": [],
                "note": ("viral checklist judge returned an "
                         "incomplete answer set — abstained")}
    answers = [by_q[i] for i in range(1, len(VIRAL_QUESTIONS) + 1)]
    return {"ai_used": True,
            "passed": all(a["pass"] for a in answers),
            "answers": answers}


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


def check_video(path, min_duration_s=None, max_duration_s=None,
                expect_audio=True,
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
    if (duration is not None and duration > 0
            and max_duration_s is not None
            and duration > max_duration_s):
        flags.append(
            f"video too long: {duration}s > {max_duration_s}s "
            "— DURATION GATE: the 30s golden formula is a hard "
            "standard, not a target (VIRAL-PROTOCOL §2/§4)")
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

    viral = viral_checklist(script, package.get("video_prompt"))
    if viral["ai_used"]:
        for i, answer in enumerate(viral["answers"], start=1):
            mark = "PASS" if answer["pass"] else "FAIL"
            line = (f"viral Q{i} [{mark}]: {answer['reason']}")
            if answer["pass"]:
                warnings.append(line)
            else:
                reasons.append(
                    f"viral checklist failed Q{i} "
                    f"({answer['question'].split(' — ')[0]}): "
                    f"{answer['reason']}")
    else:
        warnings.append(
            f"viral checklist abstained: {viral.get('note', '')}")

    media_qa = None
    if package.get("video_path"):
        media_qa = check_video(
            package["video_path"],
            max_duration_s=MAX_VIDEO_DURATION_S)
        reasons.extend(media_qa["flags"])

    passed = len(reasons) == 0
    verdict = {"passed": passed, "reasons": reasons,
               "warnings": warnings, "text_qa": text_qa,
               "critic": critic, "viral_checklist": viral,
               "media_qa": media_qa}

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
    viral = verdict.get("viral_checklist") or {}
    media = verdict.get("media_qa") or {}
    media_facts = media.get("facts") if media else None
    duration_gate = None
    if media_facts:
        measured = media_facts.get("duration_s")
        duration_gate = {
            "measured_s": measured,
            "max_s": MAX_VIDEO_DURATION_S,
            "passed": (measured is not None
                       and 0 < measured <= MAX_VIDEO_DURATION_S),
        }
    return {
        "passed": verdict["passed"],
        "reasons": verdict["reasons"],
        "warnings": verdict["warnings"],
        "critic_score": critic.get("score"),
        "viral_checklist": {
            "ai_used": viral.get("ai_used", False),
            "passed": viral.get("passed"),
            "answers": viral.get("answers", []),
        },
        "media_facts": media_facts,
        "duration_gate": duration_gate,
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
