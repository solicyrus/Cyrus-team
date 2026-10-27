"""CYRUS TEAM — smart_agents/director_agent.py

🎬 THE CONTENT DIRECTOR (Senior).

Charter job: turn an idea into a professional, publishable
package — hook-first script, precise image/audio prompts, a real
voice, and a real rendered video. NO weak or half-finished content
passes this agent; the output contract is enforced in code.

Capabilities (all real, all in this file):
1. SCRIPT — hook-first package writing on the THINKING tier
   (merged/upgraded from the old factory's hook_master +
   scriptwriter + storyboarder + title/caption/hashtag robots,
   which ran on a mini model and never enforced their output).
   A result missing hook/title/script is REJECTED here. The
   30s formula is enforced as a HARD beat word budget,
   calibrated to Piper's measured speaking rate (see §1b): an
   over-budget script is REJECTED before anything is rendered —
   the formula is a standard, not a target (fix order
   2026-10-27, after draft a4f904cd rendered 34.5s).
2. PROMPTS — one precise image prompt + a scene-by-scene video
   production prompt (for external tools; this agent writes
   prompts, it does not pretend they are media).
3. IMAGE — the proven Imagen maker (reused from URT
   robots/image_maker.py): Gemini prompt + Imagen 3 render, with
   its honest billing/skip behaviour intact.
4. VOICE — REAL offline Piper TTS (NEW: the old team had no voice
   module in-repo; shipped voices were run by hand). Fails LOUDLY
   (PiperNotConfiguredError) when the binary/voice is missing —
   a missing voice never becomes a silent "success".
5. FOOTAGE BANK — a probed catalogue of the team's real clips
   (replaces the old markdown bank + hardcoded renderer
   overrides) with the NO-LOOPING LAW enforced in code.
6. RENDERER — ffmpeg assembly of DISTINCT clips + voice + music
   into a vertical video, with the real duration measured by
   ffprobe afterwards. (Rework of the old video_finisher.py with
   its core sin removed: the finisher forced 30s by looping one
   ~10s clip ×3 — banned forever by Cyrus on 2026-10-26.)

Two-state rule: execute for real, or report «نمی‌شه» — loudly.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from smart_agents import common  # noqa: E402
from smart_agents.channels import channels_text  # noqa: E402
from smart_agents.facts import APPROVED_FACTS  # noqa: E402

log = common.get_logger("director")

# ==================================================================
# 1. SCRIPT — hook-first, contract enforced
# ==================================================================

_SCRIPT_SYSTEM = (
    "You are THE CONTENT DIRECTOR of an AI travel content team "
    "(Cyrus AI). You write short vertical videos under the "
    "VIRAL PROTOCOL's 30-SECOND GOLDEN FORMULA — every script "
    "is built on exactly four timed beats: (1) HOOK 0-3s: a "
    "visual + verbal pattern interrupt, the strongest visual "
    "and one line of clarity + surprise — no greeting, no "
    "wind-up; (2) TENSION 3-15s: fast narration, no filler, "
    "every line a new visual fact that raises a question; "
    "(3) CLIMAX 15-25s: the payoff the hook promised, cashed "
    "in specifics; (4) LOOP & CTA 25-30s: ONE decisive call to "
    "action, then a closing line written so it flows directly "
    "back into the hook line — when the video auto-replays, "
    "the sentence continues seamlessly (narrative loop; this "
    "is a words-only device, footage is never looped). "
    "HARD WORD BUDGET — the 30 seconds is a hard standard, "
    "not a target: the voice speaks a measured 2.37 words per "
    "second, so hook_0_3 is at most 7 words, tension_3_15 at "
    "most 28 words, climax_15_25 at most 23 words, "
    "loop_cta_25_30 at most 11 words, and the full script at "
    "most 69 words. Count the words in every beat as you "
    "write; an over-budget script is rejected before "
    "rendering. "
    "Scripts are spoken by a calm, confident host voice; keep "
    "sentences short and visual. " + APPROVED_FACTS + " "
    "End every description with one clear decision or call to "
    "action. Reply with ONLY valid JSON."
)

# The four beats of the golden formula, in order (VIRAL-PROTOCOL §2).
BEAT_KEYS = ("hook_0_3", "tension_3_15", "climax_15_25",
             "loop_cta_25_30")

# ==================================================================
# 1b. BEAT WORD BUDGET — the 30s formula is HARD, not a target
#
# Calibrated 2026-10-27 from a real render (draft a4f904cd,
# Piper voice en_US-amy-medium): an 82-word script produced
# 34.54s of speech = 2.374 words/second. The caps below are each
# beat's window (3s / 12s / 10s / 5s) at that measured rate,
# trimmed ~3% so a script AT the caps lands at ~29s of voice —
# inside the protocol's 28-30s landing zone. write_script()
# validates every script against this budget and REJECTS an
# over-budget one before anything is rendered (Cyrus's fix
# order, 2026-10-27: zero tolerance — the formula is hard).
# ==================================================================

PIPER_WORDS_PER_SECOND = 2.374  # measured 2026-10-27, draft a4f904cd

BEAT_WORD_BUDGET = {
    "hook_0_3": 7,         # 3s window  (7 words  ≈ 2.9s)
    "tension_3_15": 28,    # 12s window (28 words ≈ 11.8s)
    "climax_15_25": 23,    # 10s window (23 words ≈ 9.7s)
    "loop_cta_25_30": 11,  # 5s window  (11 words ≈ 4.6s)
}
MAX_SCRIPT_WORDS = sum(BEAT_WORD_BUDGET.values())  # 69 ≈ 29.1s


def count_words(text):
    """Whitespace-token word count — the same measure the
    calibration render (draft a4f904cd) was counted with."""
    return len(re.findall(r"\S+", text or ""))


def beat_budget_violations(script):
    """Word-budget violations for a script package dict.

    Returns a list of human-readable violations (empty list =
    within budget). Every beat is checked against
    BEAT_WORD_BUDGET and the assembled spoken script against
    MAX_SCRIPT_WORDS.
    """
    script = script or {}
    beats = script.get("beats") or {}
    violations = []
    for key in BEAT_KEYS:
        words = count_words(beats.get(key, ""))
        cap = BEAT_WORD_BUDGET[key]
        if words > cap:
            violations.append(
                f"beat {key} is {words} words (budget {cap})")
    total = count_words(script.get("script", ""))
    if total > MAX_SCRIPT_WORDS:
        violations.append(
            f"full script is {total} words "
            f"(budget {MAX_SCRIPT_WORDS})")
    return violations


def _write_script_once(idea, target_seconds=30, feedback=""):
    """ONE attempt at a complete script package for one idea.

    `idea`: {"hook", "title", "angle", "topic", ...} (Mastermind
    format). `feedback` is appended to the prompt (the retry in
    write_script() passes the budget violations of the previous
    attempt there). Returns {"ok": True, "script": {...}} — or
    {"ok": False, "error": ...} on honest failure, with
    "budget_violations" set when the script broke the hard beat
    word budget (§1b).
    """
    idea = idea or {}
    seed_hook = str(idea.get("hook", "")).strip()
    title = str(idea.get("title", "")).strip()
    angle = str(idea.get("angle", "")).strip()
    loop_hint = str(idea.get("loop", "")).strip()
    if not seed_hook and not title:
        return {"ok": False,
                "error": "idea has neither hook nor title — "
                         "nothing to direct"}
    prompt = (
        f"Video idea:\n- seed hook: {seed_hook}\n- title: {title}\n"
        f"- angle: {angle}\n- loop concept from the strategist: "
        f"{loop_hint or '(design one)'}\n- target length: about "
        f"{target_seconds} seconds of speech\n\n"
        "Write the full package as JSON with EXACTLY these fields:\n"
        '- "hook": the exact first-2-seconds line (may refine the '
        "seed hook, keep it explosive and honest)\n"
        '- "title": the video title\n'
        '- "beats": an object with the four golden-formula beats, '
        "each the exact spoken text for that segment. STRICT "
        "WORD CAPS per beat (the voice speaks a measured 2.37 "
        "words/second and the 30s formula is a hard standard — "
        "an over-cap beat is rejected before rendering):\n"
        '  "hook_0_3" (0-3s pattern interrupt, MAX 7 words — '
        "must open with the hook line),\n"
        '  "tension_3_15" (3-15s fast story, no filler, '
        'MAX 28 words),\n'
        '  "climax_15_25" (15-25s payoff in specifics, '
        'MAX 23 words),\n'
        '  "loop_cta_25_30" (25-30s, MAX 11 words: ONE decisive '
        "call to action, then a final line that flows straight "
        "back into the hook line so a replay feels seamless)\n"
        '- "script": the full spoken script — the four beats joined '
        "in order, MAX 69 words total\n"
        '- "on_screen_text": short text overlays in order, '
        "comma-separated\n"
        '- "caption": a short social caption\n'
        '- "description": a fuller description that ends with a '
        "call to action and may reference our channels:\n"
        + channels_text() + "\n"
        '- "hashtags": a list of 5-10 relevant hashtags (no #)\n'
        "Count the words in every beat before replying. "
        "Reply ONLY valid JSON." + feedback
    )
    data, ok = common.ask_json(prompt, _SCRIPT_SYSTEM,
                               role="thinking",
                               max_tokens=1400, temperature=0.6)
    if not ok or not data:
        return {"ok": False,
                "error": ("AI unavailable (no key / no network / "
                          "bad response) — no script written, "
                          "none faked")}
    raw_beats = data.get("beats") or {}
    beats = {k: str(raw_beats.get(k, "")).strip() for k in BEAT_KEYS}
    script = {
        "hook": str(data.get("hook", "")).strip(),
        "title": str(data.get("title", "")).strip(),
        "script": str(data.get("script", "")).strip(),
        "beats": beats,
        "on_screen_text": str(data.get("on_screen_text", "")).strip(),
        "caption": str(data.get("caption", "")).strip(),
        "description": str(data.get("description", "")).strip(),
        "hashtags": [str(h).strip().lstrip("#")
                     for h in (data.get("hashtags") or [])
                     if str(h).strip()],
    }
    missing = [k for k in ("hook", "title", "script") if not script[k]]
    missing_beats = [k for k in BEAT_KEYS if not beats[k]]
    if missing_beats:
        missing.append("beats." + ", beats.".join(missing_beats))
    if missing:
        return {"ok": False,
                "error": ("AI returned an incomplete package "
                          f"(missing: {', '.join(missing)}) — "
                          "rejected by the Content Director")}
    violations = beat_budget_violations(script)
    if violations:
        return {"ok": False, "budget_violations": violations,
                "error": ("script broke the hard beat word "
                          "budget: " + "; ".join(violations))}
    return {"ok": True, "script": script}


def write_script(idea, target_seconds=30):
    """Write a complete script package for one idea.

    `idea`: {"hook", "title", "angle", "topic", ...} (Mastermind
    format). Returns {"ok": True, "script": {hook, title, script,
    beats, on_screen_text, caption, description, hashtags}} — or
    {"ok": False, "error": ...} on honest failure.

    The HARD beat word budget (§1b) is enforced here: a first
    draft that breaks it is retried ONCE with the violations fed
    back to the writer; a script still over budget after the
    retry is REJECTED — before rendering, always. The 30s
    formula is a standard, not a target (VIRAL-PROTOCOL §2).
    """
    feedback = ""
    last = None
    for attempt in (1, 2):
        result = _write_script_once(
            idea, target_seconds=target_seconds, feedback=feedback)
        if result.get("ok") or not result.get("budget_violations"):
            return result
        last = result
        log.warning("script over word budget (attempt %d): %s",
                    attempt, "; ".join(result["budget_violations"]))
        feedback = (
            "\n\nREWRITE — your previous draft was REJECTED for "
            "breaking the hard word budget: "
            + "; ".join(result["budget_violations"])
            + ". Write the same package again with FEWER words: "
              "keep the hook explosive, keep ONE decisive call "
              "to action, keep the final line re-entering the "
              "hook — but count every word and stay under every "
              "cap.")
    return {"ok": False,
            "error": ("script exceeded the hard beat word budget "
                      "after 2 attempts ("
                      + "; ".join(last["budget_violations"])
                      + ") — REJECTED by the Content Director "
                        "before rendering (VIRAL-PROTOCOL §2: "
                        "the 30s formula is hard, not a target)")}


# ==================================================================
# 2. PROMPTS — precise image / video production prompts
# ==================================================================

_IMAGE_PROMPT_SYSTEM = (
    "You write image-generation prompts for a travel brand. Output "
    "ONE detailed English prompt: photorealistic, cinematic, "
    "vibrant natural light, vertical-friendly composition, no text "
    "or words inside the image. Reply with ONLY the prompt text."
)

_VIDEO_PROMPT_SYSTEM = (
    "You write ULTRA-DETAILED CINEMATIC production prompts for "
    "short vertical travel videos (9:16), to the standard in "
    "VIRAL-PROTOCOL.md §3 — reusable assets for Sora / Runway / "
    "Kling / Luma class video models. Every shot prompt must "
    "specify: camera movement, cinematic lighting (source, "
    "direction, colour feel), lens character, texture/surface "
    "detail, exact subject motion, and vertical composition. "
    "Every shot also gets a NEGATIVE prompt excluding warped or "
    "morphing subjects, deformed hands/faces, gibberish text, "
    "cartoon/CGI look, cheap stock look, flicker and watermarks. "
    "Photorealistic, real-world texture, no cheap artificial "
    "effects. No invented facts about places. Reply with ONLY "
    "valid JSON."
)

# The global negative prompt every package carries
# (VIRAL-PROTOCOL.md §3) — per-shot negatives extend it.
GLOBAL_NEGATIVE_PROMPT = (
    "warped or morphing subjects, deformed hands, deformed "
    "faces, extra fingers, gibberish or warped text, cartoon "
    "look, CGI look, cheap stock-photo look, oversaturated "
    "colours, flicker, temporal inconsistency, watermark, logo "
    "artefacts, low resolution, blurry"
)


def build_image_prompt(script):
    """One detailed English image prompt for a script package."""
    script = script or {}
    basis = (script.get("title", "") + ". "
             + script.get("script", "")[:400]).strip()
    if not basis:
        return {"ok": False,
                "error": "script has no title/text to prompt from"}
    text, ok = common.ask(
        "Write the image prompt for this video:\n" + basis,
        _IMAGE_PROMPT_SYSTEM, role="volume",
        max_tokens=300, temperature=0.5)
    if not ok or not text:
        return {"ok": False,
                "error": ("AI unavailable — no image prompt "
                          "produced, none faked")}
    return {"ok": True, "prompt": text}


def build_video_prompt(script, scenes=4):
    """A structured, shot-by-shot CINEMATIC production prompt.

    One shot per golden-formula beat by default (4). Each shot
    carries the full VIRAL-PROTOCOL §3 spec — prompt, camera,
    lighting, lens, texture, subject_motion, negative_prompt —
    plus the package-level global negative prompt. The "prompt"
    field stays for consumers written before this upgrade.
    """
    script = script or {}
    beats = script.get("beats") or {}
    beats_text = " ".join(
        f"[{k}] {beats[k]}" for k in BEAT_KEYS if beats.get(k))
    basis = (script.get("title", "") + ". "
             + (beats_text or script.get("script", "")[:600])).strip()
    if not basis:
        return {"ok": False,
                "error": "script has no title/text to prompt from"}
    prompt = (
        "Video package (title + timed beats):\n" + basis + "\n\n"
        f"Break it into {scenes} shots, one per beat in order. "
        "Durations follow the beats: shot 1 = 3s, shot 2 = 12s, "
        "shot 3 = 10s, shot 4 = 5s (adjust only if scenes != 4). "
        "Reply ONLY valid JSON: "
        '{"scenes": [{"scene": 1, "beat": "hook_0_3", '
        '"duration_s": 3, "prompt": "full cinematic description", '
        '"camera": "camera movement", "lighting": "lighting '
        'design", "lens": "lens character", "texture": "surface '
        'texture detail", "subject_motion": "exact subject '
        'motion", "negative_prompt": "shot-specific exclusions"'
        '}], "style": "one line of overall visual style", '
        '"negative_prompt": "package-level exclusions"}'
    )
    data, ok = common.ask_json(prompt, _VIDEO_PROMPT_SYSTEM,
                               role="volume",
                               max_tokens=1400, temperature=0.5)
    if not ok or not data or not data.get("scenes"):
        return {"ok": False,
                "error": ("AI unavailable or unusable response — "
                          "no video prompt produced, none faked")}
    clean_scenes = []
    for i, raw in enumerate(data["scenes"]):
        if not isinstance(raw, dict):
            continue
        clean_scenes.append({
            "scene": raw.get("scene", i + 1),
            "beat": str(raw.get("beat", "")).strip(),
            "duration_s": raw.get("duration_s"),
            "prompt": str(raw.get("prompt", "")).strip(),
            "camera": str(raw.get("camera", "")).strip(),
            "lighting": str(raw.get("lighting", "")).strip(),
            "lens": str(raw.get("lens", "")).strip(),
            "texture": str(raw.get("texture", "")).strip(),
            "subject_motion": str(raw.get("subject_motion",
                                       "")).strip(),
            "negative_prompt": str(
                raw.get("negative_prompt", "")).strip(),
        })
    if not clean_scenes:
        return {"ok": False,
                "error": ("AI returned no usable scenes — no "
                          "video prompt produced, none faked")}
    negative = (str(data.get("negative_prompt", "")).strip()
                or GLOBAL_NEGATIVE_PROMPT)
    return {"ok": True, "video_prompt": {
        "scenes": clean_scenes,
        "style": str(data.get("style", "")).strip(),
        "negative_prompt": negative,
    }}


# ==================================================================
# 3. IMAGE — Imagen maker (reused from URT robots/image_maker.py)
# ==================================================================

def _gemini_client():
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return None, "GEMINI_API_KEY not set"
    try:
        from google import genai
    except ImportError:
        return None, ("google-genai library not installed "
                      "(pip install google-genai)")
    try:
        return genai.Client(api_key=key), None
    except Exception as e:
        return None, f"could not create Gemini client: {type(e).__name__}: {e}"


def make_post_image(post_text, output_path="temp_image.png"):
    """Generate a 1:1 PNG visual for a post via Gemini + Imagen 3.

    Returns {"ok": True, "path", "prompt"} only when the image was
    really generated and saved; otherwise an honest skip/error
    (Imagen typically needs a billing-enabled key — that real
    error is surfaced, never hidden). Never raises.
    """
    client, problem = _gemini_client()
    if client is None:
        return {"ok": False, "skipped": True,
                "reason": f"image generation skipped — {problem}; "
                          "nothing was created"}
    try:
        prompt_resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Based on this instagram post, write a highly detailed, "
                "photorealistic, cinematic prompt in English for an AI image "
                "generator. The image should be vibrant, natural, and perfect "
                "for an outdoor adventure Instagram page. "
                "Return ONLY the english prompt:\n\n" + post_text
            ),
        )
        image_prompt = (prompt_resp.text or "").strip()
        if not image_prompt:
            return {"ok": False,
                    "reason": "Gemini returned an empty image prompt"}
        from google.genai import types
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=image_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
                aspect_ratio="1:1",
            ),
        )
        images = getattr(result, "generated_images", None) or []
        if not images:
            return {"ok": False,
                    "reason": "Imagen returned no images",
                    "prompt": image_prompt}
        images[0].image.save(output_path)
        return {"ok": True, "path": output_path, "prompt": image_prompt}
    except Exception as e:  # never raise; report the REAL error
        return {"ok": False,
                "error": f"{type(e).__name__}: {e}",
                "note": ("If this mentions billing/permission, the "
                         "Gemini key needs billing enabled for Imagen.")}


# ==================================================================
# 4. VOICE — Piper TTS, real and loud on failure
# ==================================================================

class PiperNotConfiguredError(RuntimeError):
    """Raised when the Piper binary or voice model cannot be
    found — the loud failure the charter demands."""


def _candidate_binaries():
    cands = []
    env_bin = (os.environ.get("PIPER_BIN") or "").strip()
    if env_bin:
        cands.append(env_bin)
    import shutil
    on_path = shutil.which("piper")
    if on_path:
        cands.append(on_path)
    cands.append(os.path.expanduser("~/piper/piper"))
    cands.extend(sorted(glob.glob(os.path.expanduser(
        "~/workspace/agents/*/piper/piper"))))
    return cands


def _candidate_models(binary):
    cands = []
    env_model = (os.environ.get("PIPER_MODEL") or "").strip()
    if env_model:
        cands.append(env_model)
    if binary:
        base = os.path.dirname(os.path.abspath(binary))
        cands.extend(sorted(glob.glob(os.path.join(
            base, "voices", "*.onnx"))))
        cands.extend(sorted(glob.glob(os.path.join(base, "*.onnx"))))
    cands.extend(sorted(glob.glob(os.path.expanduser(
        "~/workspace/agents/*/voices/*.onnx"))))
    cands.extend(sorted(glob.glob(os.path.expanduser(
        "~/workspace/agents/*/piper/voices/*.onnx"))))
    cands.append(os.path.expanduser(
        "~/piper/voices/en_US-amy-medium.onnx"))
    return cands


def find_piper():
    """Locate (binary, model) or return (None, None)."""
    binary = None
    for cand in _candidate_binaries():
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            binary = cand
            break
    model = None
    for cand in _candidate_models(binary):
        if cand and os.path.isfile(cand):
            model = cand
            break
    return binary, model


def voice_status():
    """Honest readiness report for the voice."""
    binary, model = find_piper()
    return {"configured": bool(binary and model),
            "binary": binary, "model": model}


def synthesize(text, out_wav, length_scale=None):
    """Speak `text` into `out_wav` with Piper. REAL synthesis.

    Returns {"ok": True, "path", "duration_s", "model"}.
    Raises PiperNotConfiguredError when Piper or the voice is
    missing; returns {"ok": False, "error"} when Piper ran but
    failed or produced an empty file.
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text — nothing to say"}
    binary, model = find_piper()
    if not binary or not model:
        tried = _candidate_binaries() + _candidate_models(binary)
        raise PiperNotConfiguredError(
            "Piper TTS not configured (نمی‌شه: صدا پیدا نشد) — "
            f"binary found: {binary!r}, model found: {model!r}. "
            "Set PIPER_BIN and PIPER_MODEL, or install Piper with a "
            f"voice model. Tried: {tried}")
    cmd = [binary, "--model", model, "--output_file", out_wav]
    if length_scale:
        cmd += ["--length_scale", str(length_scale)]
    try:
        proc = subprocess.run(cmd, input=text.encode("utf-8"),
                              capture_output=True, timeout=120)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if proc.returncode != 0:
        return {"ok": False,
                "error": ("piper exited "
                          f"{proc.returncode}: "
                          + proc.stderr.decode("utf-8", "replace")
                          [:300])}
    if not os.path.isfile(out_wav) or os.path.getsize(out_wav) == 0:
        return {"ok": False,
                "error": "piper reported success but produced no audio"}
    try:
        with wave.open(out_wav, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
        duration = frames / float(rate)
    except Exception:
        duration = None
    log.info("voice synthesized: %s (%.2fs)", out_wav, duration or -1)
    return {"ok": True, "path": out_wav, "duration_s": duration,
            "model": os.path.basename(model)}


# ==================================================================
# 5. FOOTAGE BANK — probed catalogue, NO LOOPING enforced
#
# Standing exclusions (Cyrus's orders, from the video bank):
# - 3768a798 — Hole-in-the-Wall promo, burned-in legacy price.
# - 6b00db06 — 3D cartoon trampoline clip, not beach material.
# Caution: f2dfbae4 — casino walk-through.
# ==================================================================

EXCLUDED_IDS = {"3768a798", "6b00db06"}
CAUTION_IDS = {"f2dfbae4"}
DEFAULT_BANK_DIR = os.path.expanduser(
    "~/workspace/user/media_library/video")
VIDEO_EXTS = (".mp4", ".mov", ".m4v")


class InsufficientFootageError(RuntimeError):
    """Raised when distinct bank footage cannot cover a target
    duration — the honest «نمی‌شه» instead of a looped fake."""


def probe_clip(path):
    """ffprobe one file. Returns {duration_s, width, height,
    has_audio} or None when the file cannot be probed."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, timeout=30)
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    video = None
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video is None:
            video = stream
        elif stream.get("codec_type") == "audio":
            has_audio = True
    if video is None:
        return None
    try:
        duration = float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    return {"duration_s": round(duration, 3),
            "width": video.get("width"),
            "height": video.get("height"),
            "has_audio": has_audio}


class FootageBank:
    """The clip catalogue for one bank directory."""

    def __init__(self, root=None):
        self.root = os.path.abspath(
            root or os.environ.get("CYRUS_FOOTAGE_DIR")
            or DEFAULT_BANK_DIR)
        self.clips = []

    def scan(self):
        """Probe every video file under the bank root. Unreadable
        files are recorded with probe_error, never hidden."""
        clips = []
        if not os.path.isdir(self.root):
            self.clips = []
            return {"ok": False, "root": self.root, "clips": [],
                    "error": f"bank directory not found: {self.root}"}
        for dirpath, _dirs, files in os.walk(self.root):
            for name in sorted(files):
                if not name.lower().endswith(VIDEO_EXTS):
                    continue
                path = os.path.join(dirpath, name)
                clip_id = os.path.splitext(name)[0][:8]
                entry = {
                    "id": clip_id,
                    "path": path,
                    "rights": "cyrus_owned",
                    "excluded": clip_id in EXCLUDED_IDS,
                    "caution": clip_id in CAUTION_IDS,
                }
                info = probe_clip(path)
                if info is None:
                    entry["probe_error"] = "ffprobe could not read file"
                    entry["duration_s"] = 0.0
                else:
                    entry.update(info)
                clips.append(entry)
        clips.sort(key=lambda c: c["id"])
        self.clips = clips
        log.info("footage bank: %d clips, %d usable at %s",
                 len(clips), len(self.usable()), self.root)
        return {"ok": True, "root": self.root, "clips": clips,
                "count": len(clips),
                "usable_count": len(self.usable())}

    def usable(self):
        """Distinct, non-excluded, non-caution, readable clips."""
        return [c for c in self.clips
                if not c.get("excluded") and not c.get("caution")
                and c.get("duration_s", 0) > 0
                and not c.get("probe_error")]

    def total_usable_seconds(self):
        return round(sum(c["duration_s"] for c in self.usable()), 3)

    def _build_plan(self, target_s, clips):
        chosen = []
        total = 0.0
        for clip in clips:
            if total >= target_s:
                break
            remaining = round(target_s - total, 3)
            segment = min(clip["duration_s"], remaining)
            chosen.append({
                "id": clip["id"], "path": clip["path"],
                "segment_s": segment,
                "source_duration_s": clip["duration_s"],
            })
            total = round(total + segment, 3)
        return {"clips": chosen, "target_s": target_s,
                "total_s": total, "looping": False}

    def plan(self, target_s):
        """Plan distinct footage covering target_s seconds.
        Raises InsufficientFootageError — with the honest totals —
        when the bank cannot cover it. NEVER loops."""
        if not self.clips:
            self.scan()
        available = self.total_usable_seconds()
        if available < target_s:
            raise InsufficientFootageError(
                f"نمی‌شه: distinct usable footage is {available}s "
                f"but the target is {target_s}s — looping is "
                "forbidden, so this render cannot be planned "
                "honestly. Add real footage or lower the target.")
        return self._build_plan(target_s, self.usable())

    def honest_plan(self, target_s):
        """Like plan(), but returns the true shorter plan with
        its shortfall stated instead of raising."""
        if not self.clips:
            self.scan()
        plan = self._build_plan(target_s, self.usable())
        plan["shortfall_s"] = round(target_s - plan["total_s"], 3)
        plan["honest"] = plan["shortfall_s"] <= 0
        return plan


# ==================================================================
# 6. RENDERER — ffmpeg, distinct clips, honest measured duration
# ==================================================================

RENDER_WIDTH = 1080
RENDER_HEIGHT = 1920
RENDER_FPS = 30


def render(plan, out_path, voice_wav=None, music_path=None,
           width=RENDER_WIDTH, height=RENDER_HEIGHT):
    """Render a footage plan to out_path.

    plan: {"clips": [{"path", "segment_s"}], "total_s": ...}.
    Every clip is used EXACTLY ONCE (this function never passes
    -stream_loop to ffmpeg). The voice WAV is the primary audio;
    an optional music file is mixed under it at low volume. With
    no audio inputs the output honestly has no audio stream
    (has_audio=False — Strict QA will flag it).

    Returns {"ok": True, "path", "duration_s" (ffprobe-measured),
    "planned_s", "width", "height", "has_audio"} or
    {"ok": False, "error"}. Never raises.
    """
    clips = (plan or {}).get("clips") or []
    if not clips:
        return {"ok": False,
                "error": "empty render plan — no clips to assemble"}
    for clip in clips:
        if not os.path.isfile(clip.get("path", "")):
            return {"ok": False,
                    "error": f"clip file missing: {clip.get('path')}"}
    if voice_wav and not os.path.isfile(voice_wav):
        return {"ok": False, "error": f"voice file missing: {voice_wav}"}
    if music_path and not os.path.isfile(music_path):
        return {"ok": False, "error": f"music file missing: {music_path}"}

    inputs = []
    filters = []
    for i, clip in enumerate(clips):
        inputs += ["-i", clip["path"]]
        seg = float(clip["segment_s"])
        filters.append(
            f"[{i}:v]trim=duration={seg},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio="
            f"increase,crop={width}:{height},fps={RENDER_FPS},"
            f"setsar=1,format=yuv420p[v{i}]")
    n = len(clips)
    concat_in = "".join(f"[v{i}]" for i in range(n))
    filters.append(f"{concat_in}concat=n={n}:v=1:a=0[vout]")

    audio_map = None
    next_idx = n
    voice_idx = music_idx = None
    if voice_wav:
        inputs += ["-i", voice_wav]
        voice_idx = next_idx
        next_idx += 1
    if music_path:
        inputs += ["-i", music_path]
        music_idx = next_idx
        next_idx += 1
    if voice_idx is not None and music_idx is not None:
        filters.append(
            f"[{music_idx}:a]volume=0.15[mus];"
            f"[{voice_idx}:a][mus]amix=inputs=2:duration=first[aout]")
        audio_map = "[aout]"
    elif voice_idx is not None:
        audio_map = f"{voice_idx}:a"
    elif music_idx is not None:
        audio_map = f"{music_idx}:a"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio_map:
        cmd += ["-map", audio_map, "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out_path]

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=600)
    except FileNotFoundError:
        return {"ok": False, "error": "ffmpeg not found on this system"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if proc.returncode != 0:
        return {"ok": False,
                "error": ("ffmpeg failed (exit "
                          f"{proc.returncode}): "
                          + proc.stderr.decode("utf-8", "replace")
                          [-400:])}
    info = probe_clip(out_path)
    if info is None:
        return {"ok": False,
                "error": "render finished but ffprobe cannot read "
                         "the output — not claiming success"}
    log.info("rendered %s: %.2fs (planned %s)",
             out_path, info["duration_s"], (plan or {}).get("total_s"))
    return {"ok": True, "path": out_path,
            "duration_s": info["duration_s"],
            "planned_s": (plan or {}).get("total_s"),
            "width": info["width"], "height": info["height"],
            "has_audio": info["has_audio"]}


# ==================================================================
# Agent facade + CLI
# ==================================================================

class DirectorAgent:
    """The Content Director as one callable agent."""

    def __init__(self, bank=None):
        self.bank = bank or FootageBank()

    def build_package(self, idea, target_seconds=30,
                      make_image=False, workdir=None):
        """idea -> full content package.

        The package is only "ok" when the script contract holds.
        Image generation is attempted only when asked, and its
        honest result (including skips) is recorded — a skipped
        image never blocks or fakes anything.
        """
        written = write_script(idea, target_seconds=target_seconds)
        if not written["ok"]:
            return {"ok": False, "stage": "script",
                    "error": written["error"]}
        script = written["script"]
        image_prompt = build_image_prompt(script)
        video_prompt = build_video_prompt(script)
        package = {
            "idea": idea,
            "script": script,
            "image_prompt": (image_prompt.get("prompt")
                             if image_prompt.get("ok") else None),
            "image_prompt_error": (None if image_prompt.get("ok")
                                   else image_prompt.get("error")),
            "video_prompt": (video_prompt.get("video_prompt")
                             if video_prompt.get("ok") else None),
            "video_prompt_error": (None if video_prompt.get("ok")
                                   else video_prompt.get("error")),
            "image": None,
            "video_path": None,
        }
        if make_image:
            out = None
            if workdir:
                os.makedirs(workdir, exist_ok=True)
                out = os.path.join(workdir, "post_image.png")
            package["image"] = make_post_image(
                script["caption"] or script["title"],
                output_path=out or "post_image.png")
        return {"ok": True, "package": package}

    def speak(self, text, out_wav, length_scale=None):
        return synthesize(text, out_wav, length_scale=length_scale)

    def plan_footage(self, target_s):
        return self.bank.plan(target_s)

    def render(self, plan, out_path, voice_wav=None, music_path=None):
        return render(plan, out_path, voice_wav=voice_wav,
                      music_path=music_path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The Content Director — content agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("voice-status", help="is Piper configured?")
    p_voice = sub.add_parser("voice", help="synthesize text to WAV")
    p_voice.add_argument("text")
    p_voice.add_argument("out")
    p_bank = sub.add_parser("bank", help="scan the footage bank")
    p_bank.add_argument("--root", default=None)
    args = parser.parse_args(argv)

    if args.cmd == "voice-status":
        result = voice_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["configured"] else 1
    if args.cmd == "voice":
        result = synthesize(args.text, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    bank = FootageBank(args.root)
    result = bank.scan()
    summary = {k: result.get(k) for k in
               ("ok", "root", "count", "usable_count", "error")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
