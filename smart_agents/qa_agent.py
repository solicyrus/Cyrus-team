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
3b. VISUAL QA — the gate gains EYES (Cyrus's binding order,
   2026-10-27). Until today QA read the script and probed the
   file but never LOOKED at the picture: a Las Vegas script was
   rendered over orca-whale footage and passed every gate. Now
   frames are sampled from the render and judged by the vision
   tier against the script's topic and keyword set. Cyrus's
   standard is 100%: the package passes only when EVERY sampled
   frame shows the topic's world, and the verdict records the
   checklist answer verbatim — "Visual match: does the footage
   match the script's topic and words 100%? YES/NO — evidence:
   …". The same check screens individual candidate clips BEFORE
   a render (the developer's topic-matched sourcing calls
   clip_visual_check). When the vision judge cannot run, the
   visual gate ABSTAINS (passed=None) — it never fabricates a
   verdict.

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
# 3b. VISUAL QA — frames + vision judgement (Forever Protocol v2)
#
# The gate's eyes. Frames are sampled across the runtime and the
# vision tier judges each one against the script's topic and
# keyword set. Cyrus's standard is 100%: a render passes only
# when EVERY sampled frame shows the topic's world. The same
# judgement screens single candidate clips BEFORE a render
# (clip_visual_check) — but only after the FREE metadata gate in
# the developer has already admitted them (cheap checks first,
# credit last: Zero-Waste Protocol order).
# ==================================================================

VISUAL_FRAME_FRACTIONS = (0.08, 0.25, 0.42, 0.58, 0.75, 0.92)
VISUAL_QUESTION = ("Visual match: does the footage match the "
                   "script's topic and words 100%?")
CLIP_FRAME_FRACTIONS = (0.3, 0.7)

_VISUAL_SYSTEM = (
    "You are THE STRICT QA's eyes for an AI travel content team. "
    "You fact-check video frames against a script topic, answering "
    "ONLY from what is visibly in each frame — no guessing, no "
    "charity. A frame is on_topic ONLY when it clearly shows the "
    "topic's world (its places, scenery, subjects). A frame is "
    "cinematic ONLY when it looks like real, well-shot footage "
    "with a filmic feel — NOT a watermarked stock preview, not a "
    "cartoon/CGI render, not a slideshow still, not spammy "
    "low-effort content. Reply with ONLY valid JSON."
)


def sample_frames(video_path, out_dir, fractions=VISUAL_FRAME_FRACTIONS):
    """Extract JPEG frames spread across the runtime with ffmpeg.

    Returns [{"path", "t_s", "fraction"}] — possibly fewer than
    requested (short/unreadable video); [] on total failure."""
    info = probe_video(video_path)
    duration = info.get("duration_s")
    if not duration or duration <= 0:
        return []
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for i, frac in enumerate(fractions):
        t = round(duration * frac, 2)
        out = os.path.join(out_dir, f"frame_{i}_{t:.2f}s.jpg")
        try:
            proc = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t), "-i", video_path,
                 "-frames:v", "1", "-vf", "scale=512:-2",
                 "-q:v", "4", out],
                capture_output=True, timeout=60)
        except Exception:
            continue
        if (proc.returncode == 0 and os.path.isfile(out)
                and os.path.getsize(out) > 0):
            frames.append({"path": out, "t_s": t, "fraction": frac})
    return frames


def _judge_frames(frames, topic, keywords, world=None):
    """Vision-judge sampled frames against a topic.

    `world` is the visual-world anchor (the place and its
    iconic elements, derived with the footage keywords): a
    frame is on-topic when it belongs to that world. The
    script's marketing angle ("hidden gems", "secret spots")
    does NOT need to be literally visible in every frame —
    B-roll of the right place is on-topic; a different place,
    subject class or world is not.

    Returns [{"t_s", "on_topic", "cinematic", "shows"}] aligned
    with `frames`, or None when the judge could not run or
    answered incompletely (abstain — never fabricate)."""
    if not frames:
        return None
    kw = ", ".join(str(k) for k in (keywords or []) if str(k).strip())
    listing = "\n".join(
        f"image {i + 1}: frame at {f['t_s']}s"
        for i, f in enumerate(frames))
    world_line = (
        f"Required visual world: {world}\n" if world else "")
    prompt = (
        f"Script topic: {topic}\n"
        f"{world_line}"
        f"Expected visual world (keywords): {kw or topic}\n\n"
        f"{listing}\n\n"
        "For EVERY image decide:\n"
        "- on_topic: does it CLEARLY belong to the topic's "
        "visual world — the right PLACE and subject class (the "
        "required visual world above, or the places/scenery/"
        "subjects the keywords describe)? The script's angle "
        "(e.g. 'hidden gems') need not be literally visible; "
        "establishing footage of the right place IS on-topic. "
        "If it shows a different place, subject or world, "
        "on_topic=false.\n"
        "- cinematic: does it look like real, well-shot cinematic "
        "footage (not watermarked stock, not cartoon/CGI, not a "
        "cheap slideshow still)?\n"
        "- shows: a few words on what the frame ACTUALLY shows.\n"
        'Reply ONLY valid JSON: {"frames": [{"i": 1, '
        '"on_topic": true, "cinematic": true, "shows": "..."}, '
        "...]} covering every image in order."
    )
    data, ok = common.ask_vision_json(
        [f["path"] for f in frames], prompt, _VISUAL_SYSTEM,
        role="thinking", max_tokens=1200, temperature=0.1)
    if not ok or not data or not isinstance(data.get("frames"), list):
        return None
    by_i = {}
    for raw in data["frames"]:
        if isinstance(raw, dict):
            try:
                by_i[int(raw.get("i"))] = raw
            except (TypeError, ValueError):
                continue
    judged = []
    for i, f in enumerate(frames, start=1):
        raw = by_i.get(i)
        if raw is None:
            return None  # incomplete answer set — abstain
        judged.append({
            "t_s": f["t_s"],
            "on_topic": bool(raw.get("on_topic")),
            "cinematic": bool(raw.get("cinematic")),
            "shows": str(raw.get("shows", "")).strip(),
        })
    return judged


def visual_match_check(video_path, topic, keywords=None,
                       frames_dir=None, world=None):
    """The visual gate over a finished render.

    Samples >= 4 frames across the runtime and vision-judges
    them. Returns {"ran", "passed", "frames", "on_topic_count",
    "cinematic_count", "total", "answer", "note"}.
    passed=True requires EVERY sampled frame on-topic (Cyrus's
    100% standard) — and `answer` records the binding checklist
    line verbatim. ran=False / passed=None means the gate
    abstained (no verdict fabricated).
    """
    abstain = {"ran": False, "passed": None, "frames": [],
               "on_topic_count": 0, "cinematic_count": 0,
               "total": 0, "answer": None, "note": ""}
    topic = (topic or "").strip()
    if not topic:
        abstain["note"] = "no topic given — visual gate abstained"
        return abstain
    if not video_path or not os.path.isfile(video_path):
        abstain["note"] = f"video not found: {video_path}"
        return abstain
    if frames_dir is None:
        import tempfile
        frames_dir = tempfile.mkdtemp(prefix="visual_qa_")
    frames = sample_frames(video_path, frames_dir)
    if len(frames) < 4:
        abstain["note"] = (f"only {len(frames)} frames could be "
                           "sampled (need >= 4) — visual gate "
                           "abstained")
        return abstain
    judged = _judge_frames(frames, topic, keywords, world=world)
    if judged is None:
        abstain["note"] = ("vision judge unavailable or answered "
                           "incompletely — visual gate abstained "
                           "(no verdict fabricated)")
        return abstain
    total = len(judged)
    on = sum(1 for j in judged if j["on_topic"])
    cin = sum(1 for j in judged if j["cinematic"])
    passed = (on == total)
    evidence = "; ".join(
        f"{j['t_s']}s: {j['shows']}" for j in judged)
    answer = (f"{VISUAL_QUESTION} "
              f"{'YES' if passed else 'NO'} — evidence: "
              f"{on}/{total} sampled frames on-topic [{evidence}]")
    return {"ran": True, "passed": passed, "frames": judged,
            "on_topic_count": on, "cinematic_count": cin,
            "total": total, "answer": answer, "note": ""}


def clip_visual_check(clip_path, topic, keywords=None,
                      frames_dir=None, world=None):
    """Pre-render screening of ONE candidate clip (developer
    sourcing calls this AFTER the free metadata gate).

    Samples 2 frames; the clip is admitted only when the judge
    ran and BOTH frames are on-topic. Returns {"ran", "on_topic",
    "frames", "note"} — on_topic=None when the judge abstained,
    and an abstention never admits a clip.
    """
    out = {"ran": False, "on_topic": None, "frames": [], "note": ""}
    if not clip_path or not os.path.isfile(clip_path):
        out["note"] = f"clip not found: {clip_path}"
        return out
    if frames_dir is None:
        import tempfile
        frames_dir = tempfile.mkdtemp(prefix="clip_visual_")
    frames = sample_frames(clip_path, frames_dir,
                           fractions=CLIP_FRAME_FRACTIONS)
    if len(frames) < len(CLIP_FRAME_FRACTIONS):
        out["note"] = ("could not sample 2 frames from the clip "
                       "— not admitted")
        return out
    judged = _judge_frames(frames, topic, keywords, world=world)
    if judged is None:
        out["note"] = ("vision judge unavailable — clip not "
                       "admitted (no unverified footage enters a "
                       "render)")
        return out
    out["ran"] = True
    out["frames"] = judged
    out["on_topic"] = all(j["on_topic"] for j in judged)
    if not out["on_topic"]:
        bad = "; ".join(f"{j['t_s']}s: {j['shows']}"
                        for j in judged if not j["on_topic"])
        out["note"] = f"off-topic frames: {bad}"
    return out


# ==================================================================
# 3c. THE HARD GATE — Forever Protocol v2: FIVE questions
#
# THE pass/fail gate for any package with a video (Cyrus,
# Forever Protocol v2 — supersedes the v1 zero-waste 4-question
# list). The viral checklist stays as advisory scoring; THIS
# gate decides. All five answers must be YES — a single NO
# rejects the package, and a gate that cannot run also rejects
# (no untested delivery). Every answer is recorded in text.
#
# Q1 image <-> narrator's text 100%: the visual gate (every
#    sampled frame on-topic). The beat-sync measurement
#    (scene cuts vs per-beat voice boundaries, tolerance
#    ±0.75s) is recorded as evidence under this answer.
# Q2 the 3-second hook: judged by the viral checklist's hook
#    question (advisory scoring, load-bearing evidence here).
# Q3 real, clear footage: every sampled frame judged real and
#    cinematic by the vision tier — no watermarks, no cartoon,
#    no cheap effects; native-resolution sharpness is already
#    enforced at selection (developer, Law 3).
# Q4 voice & sound clean: MEASURED from the render's audio
#    (peak/RMS via ffmpeg, longest mid-video silence, speech
#    present in every beat).
# Q5 the closing verbal loop: all four beats present, the
#    final beat re-enters the hook line, duration inside the
#    golden window.
# ==================================================================

HARD_Q1 = ("Does the recorded image match the narrator's "
           "text 100%?")
HARD_Q2 = "Does the 3-second hook have thumb-stopping power?"
HARD_Q3 = ("Is the footage real, clear, and free of ugly "
           "effects?")
HARD_Q4 = ("Are the narrator voice and sound effects clean "
           "and cinematic?")
HARD_Q5 = ("Is the closing verbal loop executed smoothly?")
HARD_QUESTIONS = (HARD_Q1, HARD_Q2, HARD_Q3, HARD_Q4, HARD_Q5)

SYNC_TOLERANCE_S = 0.75
STRUCTURE_MIN_S = 29.0
STRUCTURE_MAX_S = 31.0
_BEAT_KEYS = ("hook_0_3", "tension_3_15", "climax_15_25",
              "loop_cta_25_30")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "with", "for", "is", "are", "your", "you", "it", "its",
    "that", "this", "these", "those", "just", "more",
}


def detect_scene_cuts(video_path, threshold=0.35):
    """Real cut points of a rendered file via ffmpeg scene
    detection. Returns a sorted list of timestamps (seconds,
    excluding t=0), or None when detection could not run."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", video_path, "-filter:v",
             f"select='gt(scene,{threshold})',showinfo",
             "-f", "null", "-"],
            capture_output=True, timeout=300)
    except Exception:
        return None
    text = proc.stderr.decode("utf-8", "replace")
    cuts = []
    for line in text.splitlines():
        if "showinfo" not in line or "pts_time:" not in line:
            continue
        try:
            part = line.split("pts_time:", 1)[1].split()[0]
            t = float(part)
        except (IndexError, ValueError):
            continue
        if t > 0.05:
            cuts.append(round(t, 3))
    return sorted(set(cuts))


def measure_sync(video_path, beat_boundaries_s, plan_cuts_s=None):
    """Q3's measurement. Compares the voice beat boundaries
    (seconds, cumulative, excluding 0 and the final end) with
    the render's detected scene cuts.

    Returns {"ran", "synced", "offsets": [{"beat_boundary_s",
    "nearest_cut_s", "offset_s"}], "detected_cuts_s",
    "plan_verified", "note"}. synced=True only when every beat
    boundary has a detected cut within SYNC_TOLERANCE_S.
    """
    out = {"ran": False, "synced": None, "offsets": [],
           "detected_cuts_s": None, "plan_verified": None,
           "note": ""}
    boundaries = [float(b) for b in (beat_boundaries_s or [])
                  if 0.05 < float(b)]
    info = probe_video(video_path)
    duration = info.get("duration_s")
    if duration:
        boundaries = [b for b in boundaries if b < duration - 0.05]
    if not boundaries:
        out["note"] = ("no voice beat boundaries recorded — "
                       "sync untested")
        return out
    cuts = detect_scene_cuts(video_path)
    if cuts is None:
        out["note"] = "scene detection could not run — sync untested"
        return out
    out["detected_cuts_s"] = cuts
    offsets = []
    synced = True
    for b in boundaries:
        nearest = min(cuts, key=lambda c: abs(c - b)) if cuts else None
        offset = (round(nearest - b, 3) if nearest is not None
                  else None)
        offsets.append({"beat_boundary_s": b,
                        "nearest_cut_s": nearest,
                        "offset_s": offset})
        if offset is None or abs(offset) > SYNC_TOLERANCE_S:
            synced = False
    out["offsets"] = offsets
    if plan_cuts_s is not None:
        plan_ok = True
        for p in plan_cuts_s:
            p = float(p)
            if p <= 0.05:
                continue
            if not any(abs(c - p) <= SYNC_TOLERANCE_S for c in cuts):
                plan_ok = False
        out["plan_verified"] = plan_ok
    out["ran"] = True
    out["synced"] = synced
    if not synced:
        bad = [o for o in offsets
               if o["offset_s"] is None
               or abs(o["offset_s"]) > SYNC_TOLERANCE_S]
        out["note"] = ("beat boundaries without a matching cut: "
                       + ", ".join(str(o["beat_boundary_s"])
                                   for o in bad))
    return out


def _loop_reenters_hook(script):
    """Deterministic narrative-loop check: the loop/CTA beat
    shares at least one content word with the hook line."""
    beats = (script or {}).get("beats") or {}
    hook = str(beats.get("hook_0_3") or (script or {}).get("hook")
               or "")
    loop = str(beats.get("loop_cta_25_30") or "")

    def content_words(text):
        return {w.strip(".,!?;:'\"").lower()
                for w in text.split()}
    hook_words = {w for w in content_words(hook)
                  if w and w not in _STOPWORDS}
    loop_words = {w for w in content_words(loop)
                  if w and w not in _STOPWORDS}
    return bool(hook_words & loop_words)


def measure_audio(video_path, package=None):
    """Q4's measurement: the render's audio, measured with
    ffmpeg (volumedetect + silencedetect).

    Returns {"ran", "clean", "facts": {"has_audio",
    "mean_volume_db", "max_volume_db", "longest_silence_s",
    "beats_with_speech"}, "note"}. clean=True requires: an
    audio stream, no clipping (peak <= -0.2 dB; true clipping
    is 0 dBFS), a sane mean level, no mid-video silence longer
    than 5.5s, and speech recorded in every beat (when build
    data is present).
    """
    out = {"ran": False, "clean": None, "facts": {}, "note": ""}
    facts_v = probe_video(video_path)
    if not facts_v.get("has_audio"):
        out["note"] = "no audio stream in the render"
        out["facts"] = {"has_audio": False}
        return out
    try:
        vol = subprocess.run(
            ["ffmpeg", "-i", video_path, "-map", "0:a:0",
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, timeout=300)
        text = vol.stderr.decode("utf-8", "replace")
        mean_db = max_db = None
        for line in text.splitlines():
            if "mean_volume:" in line:
                try:
                    mean_db = float(line.split("mean_volume:")[1]
                                    .split("dB")[0].strip())
                except (IndexError, ValueError):
                    pass
            if "max_volume:" in line:
                try:
                    max_db = float(line.split("max_volume:")[1]
                                   .split("dB")[0].strip())
                except (IndexError, ValueError):
                    pass
        sil = subprocess.run(
            ["ffmpeg", "-i", video_path, "-map", "0:a:0",
             "-af", "silencedetect=noise=-45dB:d=1.0",
             "-f", "null", "-"],
            capture_output=True, timeout=300)
        stext = sil.stderr.decode("utf-8", "replace")
        starts, ends = [], []
        for line in stext.splitlines():
            if "silence_start:" in line:
                try:
                    starts.append(float(
                        line.split("silence_start:")[1]
                        .split()[0].strip()))
                except (IndexError, ValueError):
                    pass
            if "silence_end:" in line:
                try:
                    ends.append(float(
                        line.split("silence_end:")[1]
                        .split()[0].strip()))
                except (IndexError, ValueError):
                    pass
    except Exception as e:
        out["note"] = f"audio measurement failed: {e}"
        return out
    duration = facts_v.get("duration_s") or 0.0
    gaps = []
    for s, e in zip(starts, ends):
        if s > 0.25 and e < duration - 0.25:
            gaps.append(round(e - s, 2))
    longest = max(gaps) if gaps else 0.0
    beats = ((package or {}).get("sync") or {}).get("beats") or []
    beats_with_speech = None
    if beats:
        beats_with_speech = all(
            (b.get("speech_s") or 0) > 0.3 for b in beats)
    facts_out = {"has_audio": True, "mean_volume_db": mean_db,
                 "max_volume_db": max_db,
                 "longest_silence_s": longest,
                 "beats_with_speech": beats_with_speech}
    out["facts"] = facts_out
    if mean_db is None or max_db is None:
        out["note"] = "volume measurement incomplete"
        return out
    # Clipping means samples AT full scale (0 dBFS); a peak of
    # -0.4 dB is hot but clean. The -0.2 line only guards
    # measurement rounding at the top.
    clean = (max_db <= -0.2 and -35.0 <= mean_db <= -10.0
             and longest <= 5.5
             and beats_with_speech is not False)
    out["ran"] = True
    out["clean"] = clean
    out["note"] = (
        f"peak {max_db} dB (clipping at 0 dBFS; fail if "
        f"> -0.2), mean {mean_db} dB, longest mid-video "
        f"silence {longest}s (limit 5.5s), speech in every "
        f"beat: {beats_with_speech}")
    return out


def hard_gate(package, visual=None, viral=None):
    """Answer Forever Protocol v2's FIVE hard questions for a
    package with a video. Returns {"ran", "passed", "answers":
    [{"q", "question", "pass", "evidence"}], "visual", "sync",
    "audio"}.

    ran=False (passed=False) when the gate itself could not be
    executed — an untested package is never delivered.
    `visual` / `viral` may carry pre-computed results to avoid
    judging twice.
    """
    package = package or {}
    script = package.get("script") or {}
    video_path = package.get("video_path")
    answers = []

    def ans(q, question, ok, evidence):
        answers.append({"q": q, "question": question,
                        "pass": bool(ok), "evidence": evidence})

    if not video_path or not os.path.isfile(video_path or ""):
        for i, qtext in enumerate(HARD_QUESTIONS, start=1):
            ans(i, qtext, False,
                f"no rendered video to inspect: {video_path}")
        return {"ran": False, "passed": False,
                "answers": answers, "visual": visual,
                "sync": None, "audio": None}

    topic = (package.get("topic")
             or (package.get("idea") or {}).get("title")
             or script.get("title") or "")
    if visual is None:
        visual = visual_match_check(
            video_path, topic, package.get("footage_keywords"),
            world=package.get("visual_world"))

    # Sync is measured once and recorded as evidence under Q1.
    sync_info = (package.get("sync") or {})
    sync = measure_sync(
        video_path, sync_info.get("beat_boundaries_s"),
        plan_cuts_s=sync_info.get("plan_cuts_s"))
    if sync.get("ran"):
        sync_line = ("sync evidence: " + ", ".join(
            f"beat {o['beat_boundary_s']}s -> cut "
            f"{o['nearest_cut_s']}s (offset {o['offset_s']}s)"
            for o in sync["offsets"])
            + f"; tolerance ±{SYNC_TOLERANCE_S}s")
    else:
        sync_line = ("sync evidence: untested — "
                     + (sync.get("note") or "unknown"))

    # Q1 — image <-> narrator's text (100%), sync as evidence.
    if visual.get("ran"):
        ans(1, HARD_Q1, bool(visual.get("passed")),
            (visual.get("answer") or "") + " | " + sync_line)
    else:
        ans(1, HARD_Q1, False,
            "visual gate could not run: "
            + (visual.get("note") or "unknown"))

    # Q2 — the hook, judged by the viral checklist's Q1.
    viral_answers = (viral or {}).get("answers") or []
    if (viral or {}).get("ai_used") and viral_answers:
        hook_a = viral_answers[0]
        ans(2, HARD_Q2, bool(hook_a.get("pass")),
            "viral checklist hook judgement: "
            + (hook_a.get("reason") or ""))
    else:
        ans(2, HARD_Q2, False,
            "hook judge (viral checklist) unavailable or "
            "abstained — thumb-stopping power untested")

    # Q3 — real, clear footage (the gate's eyes, quality side).
    if visual.get("ran"):
        cin = visual.get("cinematic_count", 0)
        total = visual.get("total", 0)
        facts_v = probe_video(video_path)
        ans(3, HARD_Q3, total > 0 and cin == total,
            f"{cin}/{total} sampled frames judged real and "
            "cinematic (no watermark/cartoon/cheap effects); "
            f"render {facts_v.get('width')}x"
            f"{facts_v.get('height')}; native sharpness "
            "enforced at selection (Law 3)")
    else:
        ans(3, HARD_Q3, False,
            "visual gate could not run — footage quality "
            "untested")

    # Q4 — voice & sound, measured.
    audio = measure_audio(video_path, package)
    if audio.get("ran"):
        ans(4, HARD_Q4, bool(audio.get("clean")),
            audio.get("note") or "")
    else:
        ans(4, HARD_Q4, False,
            "audio untested: " + (audio.get("note") or "unknown"))

    # Q5 — the closing verbal loop, executed smoothly.
    beats = script.get("beats") or {}
    beats_ok = all(str(beats.get(k) or "").strip()
                   for k in _BEAT_KEYS)
    loop_ok = _loop_reenters_hook(script)
    facts_v = probe_video(video_path)
    duration = facts_v.get("duration_s")
    dur_ok = (duration is not None
              and STRUCTURE_MIN_S <= duration <= STRUCTURE_MAX_S)
    loop_evidence = ""
    if (viral or {}).get("ai_used") and len(viral_answers) >= 4:
        loop_evidence = ("; viral loop judgement: "
                         + (viral_answers[3].get("reason") or ""))
    ans(5, HARD_Q5, beats_ok and loop_ok and dur_ok,
        f"beats complete: {beats_ok}; final beat re-enters "
        f"the hook line: {loop_ok}; duration {duration}s "
        f"inside [{STRUCTURE_MIN_S}, {STRUCTURE_MAX_S}]: "
        f"{dur_ok}{loop_evidence}")

    ran = bool(visual.get("ran"))
    return {"ran": ran,
            "passed": all(a["pass"] for a in answers),
            "answers": answers, "visual": visual, "sync": sync,
            "audio": audio}


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
        # Forever Protocol v2: the viral checklist is ADVISORY
        # scoring — its answers are recorded as warnings and
        # its hook judgement is evidence for hard gate Q2, but
        # pass/fail belongs to the HARD GATE alone.
        for i, answer in enumerate(viral["answers"], start=1):
            mark = "PASS" if answer["pass"] else "FAIL"
            line = (f"viral Q{i} [{mark}]: {answer['reason']}")
            if not answer["pass"]:
                line += " (advisory — the hard gate decides)"
            warnings.append(line)
    else:
        warnings.append(
            f"viral checklist abstained: {viral.get('note', '')}")

    media_qa = None
    visual = None
    hard = None
    if package.get("video_path"):
        media_qa = check_video(
            package["video_path"],
            max_duration_s=MAX_VIDEO_DURATION_S)
        reasons.extend(media_qa["flags"])

        # VISUAL QA + THE HARD GATE (Forever Protocol v2).
        # The visual gate looks at the picture; the hard gate's
        # five answers decide. A single NO — or a gate that
        # could not run — rejects: no untested delivery.
        topic = (package.get("topic")
                 or (package.get("idea") or {}).get("title")
                 or script.get("title") or "")
        visual = visual_match_check(
            package["video_path"], topic,
            package.get("footage_keywords"),
            world=package.get("visual_world"))
        hard = hard_gate(package, visual=visual, viral=viral)
        for answer in hard["answers"]:
            line = (f"hard gate Q{answer['q']} "
                    f"[{'YES' if answer['pass'] else 'NO'}]: "
                    f"{answer['evidence']}")
            if answer["pass"]:
                warnings.append(line)
            else:
                reasons.append(
                    f"hard gate Q{answer['q']} answered NO "
                    f"({answer['question']}): "
                    f"{answer['evidence']}")
        if not hard["ran"]:
            reasons.append(
                "hard gate could not be fully executed — "
                "untested delivery is forbidden (Forever "
                "Protocol v2)")

    passed = len(reasons) == 0
    verdict = {"passed": passed, "reasons": reasons,
               "warnings": warnings, "text_qa": text_qa,
               "critic": critic, "viral_checklist": viral,
               "media_qa": media_qa, "visual_match": visual,
               "hard_gate": hard}

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
            if hard is not None:
                common.append_error_log(
                    "QA hard-gate rejection",
                    f"package {package['id']} rejected by the "
                    "hard gate (Forever Protocol v2)",
                    "reasons: " + "; ".join(reasons))
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
    visual = verdict.get("visual_match") or {}
    hard = verdict.get("hard_gate") or {}
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
        "visual_match": {
            "ran": visual.get("ran", False),
            "passed": visual.get("passed"),
            "answer": visual.get("answer"),
            "on_topic_count": visual.get("on_topic_count"),
            "cinematic_count": visual.get("cinematic_count"),
            "total": visual.get("total"),
            "frames": visual.get("frames", []),
            "note": visual.get("note", ""),
        },
        "hard_gate": {
            "ran": hard.get("ran", False),
            "passed": hard.get("passed"),
            "answers": hard.get("answers", []),
            "sync": hard.get("sync"),
        },
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
