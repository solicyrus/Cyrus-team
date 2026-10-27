"""CYRUS TEAM — smart_agents/developer_agent.py

🛠️ THE CORE DEVELOPER (Senior) — Python development & API
integration.

Charter job: connect the agents to the social platforms and the
media tools through REAL APIs, with clean modular code, so
production and publishing are automated end to end.

Integrations (all real API code — no simulations anywhere):
1. TELEGRAM — Bot API sendMessage / sendPhoto / sendVideo.
   Reused from the proven URT `robots/telegram_publisher.py`
   (it published the team's real posts) and extended with photo
   and video sends. Clean skip when credentials are absent.
2. YOUTUBE — Data API v3 resumable upload with OAuth
   (google-auth-oauthlib flow + googleapiclient). This is the leg
   the old team NEVER had (uploads were done by hand in a
   browser). Without credentials it raises
   YouTubeNotConfiguredError with the exact missing piece —
   NEVER a fake upload.
3. INSTAGRAM — Meta Graph API two-step publish for photos AND
   Reels (adapted from URT `robots/instagram_publisher.py`,
   stdlib-only here). Local file paths are refused BEFORE any
   network call — Meta's servers must fetch a public URL.
4. WHATSAPP — the honest package builder: the channel is posted
   by Cyrus's one tap (no Business API exists for it), so this
   builds the ready-to-paste package file and says exactly that.
5. RENDER HANDLING — runs the Director's render engine for a
   package (footage plan -> voice -> render) and ffprobe-verifies
   the output before attaching it to the package.
5b. TOPIC-MATCHED FOOTAGE + ZERO-WASTE RENDER (Cyrus's binding
   order, 2026-10-27, after Critical Failure #001 — the whale
   video) — renders are built from REAL stock footage sourced
   by the script's own keywords, gated in the protocol's order:
   (a) FREE metadata gate (a clip whose metadata contradicts
   the topic's content class is STOPPED with zero further
   spend, and the stop is logged), (b) per-clip vision
   verification, (c) a beat-synced render whose scene cuts land
   on the voice beat boundaries. If topic-matched footage
   cannot cover the video, the pipeline STOPS and reports
   honestly — it never fills the gap with off-topic clips, and
   never from the topic-blind personal bank.

Credentials come ONLY from the environment / credential files
named in .env.example. Values are never printed or logged.
"""

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from smart_agents import common  # noqa: E402
from smart_agents import director_agent  # noqa: E402

log = common.get_logger("developer")

_UA = {"User-Agent": "Mozilla/5.0"}


def _http_json(url, payload=None, params=None, timeout=30):
    """POST (when payload given) or GET a JSON API. Returns
    (status, dict). Raises on transport errors — callers convert
    them into honest result dicts."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    data = None
    headers = dict(_UA)
    if payload is not None:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _http_multipart(url, fields, file_field, file_path, timeout=120):
    """POST multipart/form-data with one file (stdlib only).
    Returns (status, dict)."""
    boundary = "----cyrusteam" + uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                 f'name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    filename = os.path.basename(file_path)
    body += (f"--{boundary}\r\nContent-Disposition: form-data; "
             f'name="{file_field}"; filename="{filename}"\r\n'
             "Content-Type: application/octet-stream\r\n\r\n"
             ).encode("utf-8") + file_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type":
                 f"multipart/form-data; boundary={boundary}",
                 "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


# ==================================================================
# 1. TELEGRAM (reused publisher + photo/video sends)
# ==================================================================

_TG_API = "https://api.telegram.org/bot{token}/{method}"


def _telegram_creds(token=None, chat_id=None):
    token = (token if token is not None
             else os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = (chat_id if chat_id is not None
               else os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    return token, chat_id


def telegram_publish(text, chat_id=None, token=None):
    """Send text via the Bot API. Real result dict, never raises.
    Clean skip when credentials are absent (URT contract)."""
    token, chat_id = _telegram_creds(token, chat_id)
    if not token or not chat_id:
        return {"ok": False, "skipped": True,
                "reason": ("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
                           "not set — publish skipped, nothing "
                           "was sent")}
    try:
        data = json.dumps({"chat_id": chat_id, "text": text}
                          ).encode("utf-8")
        req = urllib.request.Request(
            _TG_API.format(token=token, method="sendMessage"),
            data=data,
            headers={"Content-Type": "application/json", **_UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            return {"ok": True,
                    "message_id": result["result"].get("message_id"),
                    "chat_id": chat_id}
        return {"ok": False,
                "error": (f"Telegram API refused: "
                          f"{result.get('description', result)}")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def telegram_publish_file(file_path, caption="", kind="video",
                          chat_id=None, token=None):
    """Send a photo or video file via the Bot API (multipart).
    kind: "video" -> sendVideo, "photo" -> sendPhoto."""
    token, chat_id = _telegram_creds(token, chat_id)
    if not token or not chat_id:
        return {"ok": False, "skipped": True,
                "reason": ("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
                           "not set — publish skipped, nothing "
                           "was sent")}
    if not os.path.isfile(file_path):
        return {"ok": False,
                "error": f"file not found: {file_path}"}
    method = "sendVideo" if kind == "video" else "sendPhoto"
    try:
        status, result = _http_multipart(
            _TG_API.format(token=token, method=method),
            {"chat_id": chat_id, "caption": caption},
            kind, file_path)
        if result.get("ok"):
            return {"ok": True,
                    "message_id": result["result"].get("message_id"),
                    "chat_id": chat_id}
        return {"ok": False,
                "error": (f"Telegram API refused: "
                          f"{result.get('description', result)}")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ==================================================================
# 2. YOUTUBE — Data API v3 upload (the leg the old team never had)
# ==================================================================

class YouTubeNotConfiguredError(RuntimeError):
    """Raised when YouTube upload credentials are absent or the
    Google client libraries are not installed — loudly, with the
    exact missing piece named. NEVER a fake upload."""


_YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def youtube_status():
    """{"configured": bool, "reason": str, "secrets_file": ...}"""
    secrets = (os.environ.get("YOUTUBE_CLIENT_SECRETS") or ""
               ).strip()
    if not secrets:
        return {"configured": False,
                "reason": ("YOUTUBE_CLIENT_SECRETS not set — "
                           "YouTube upload is not configured "
                           "(نمی‌شه yet: برای آپلود یوتیوب اول باید "
                           "OAuth ساخته شود)"),
                "secrets_file": None}
    if not os.path.isfile(secrets):
        return {"configured": False,
                "reason": f"client secrets file not found: {secrets}",
                "secrets_file": secrets}
    try:
        import googleapiclient.discovery  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
    except ImportError:
        return {"configured": False,
                "reason": ("google-api-python-client / "
                           "google-auth-oauthlib not installed "
                           "(pip install -r requirements.txt)"),
                "secrets_file": secrets}
    return {"configured": True, "reason": "", "secrets_file": secrets}


def _youtube_service():
    """Build an authenticated YouTube service or raise
    YouTubeNotConfiguredError. Runs the OAuth installed-app flow
    on first use and caches the token at YOUTUBE_TOKEN_FILE."""
    status = youtube_status()
    if not status["configured"]:
        raise YouTubeNotConfiguredError(status["reason"])
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    secrets = status["secrets_file"]
    token_file = (os.environ.get("YOUTUBE_TOKEN_FILE") or
                  os.path.join(os.path.dirname(secrets),
                               "youtube_token.json"))
    creds = None
    if os.path.isfile(token_file):
        creds = Credentials.from_authorized_user_file(
            token_file, _YT_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets, _YT_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def youtube_upload(video_path, title, description="", tags=None,
                   privacy="private"):
    """Upload a video via the YouTube Data API v3 (resumable).

    Default privacy is "private": Cyrus's standing rule is that
    videos are shown to him first — nothing goes public from this
    function without an explicit privacy argument.

    Returns {"ok": True, "video_id", "url", "privacy"} only when
    YouTube really accepted the upload. Raises
    YouTubeNotConfiguredError when credentials/libraries are
    missing; returns {"ok": False, "error"} on API failure.
    """
    if not os.path.isfile(video_path):
        return {"ok": False,
                "error": f"video file not found: {video_path}"}
    youtube = _youtube_service()  # raises loudly when unconfigured
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "19",  # Travel & Events
        },
        "status": {"privacyStatus": privacy,
                   "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, mimetype="video/*",
                            resumable=True)
    request = youtube.videos().insert(part="snippet,status",
                                      body=body, media_body=media)
    try:
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("YouTube upload: %d%%",
                         int(status.progress() * 100))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    video_id = (response or {}).get("id")
    if not video_id:
        return {"ok": False,
                "error": f"YouTube returned no video id: {response}"}
    log.info("YouTube upload complete: %s", video_id)
    return {"ok": True, "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "privacy": privacy}


# ==================================================================
# 3. INSTAGRAM — Graph API photos + Reels (public URL required)
# ==================================================================

_IG_API = "https://graph.facebook.com/v21.0"
_IG_POLL_TIMEOUT_S = 120
_IG_POLL_INTERVAL_S = 5


def _looks_public_url(value):
    v = (value or "").strip()
    return v.startswith("https://") and " " not in v


def _ig_creds(token=None, ig_user_id=None):
    token = (token if token is not None
             else os.environ.get("IG_ACCESS_TOKEN", "")).strip()
    ig_user_id = (ig_user_id if ig_user_id is not None
                  else os.environ.get("IG_USER_ID", "")).strip()
    return token, ig_user_id


def _ig_publish_container(ig_user_id, creation_id, token):
    """Poll a media container until FINISHED, then publish it."""
    import time
    deadline = time.time() + _IG_POLL_TIMEOUT_S
    status = None
    while time.time() < deadline:
        _code, s = _http_json(
            f"{_IG_API}/{creation_id}",
            params={"fields": "status_code", "access_token": token})
        status = (s.get("status_code") or "").upper()
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            return {"ok": False,
                    "error": ("media container failed on Meta's "
                              f"side: {s}")}
        time.sleep(_IG_POLL_INTERVAL_S)
    if status != "FINISHED":
        return {"ok": False,
                "error": (f"media container not ready after "
                          f"{_IG_POLL_TIMEOUT_S}s (last: {status})")}
    _code, pdata = _http_json(
        f"{_IG_API}/{ig_user_id}/media_publish",
        payload={"creation_id": creation_id, "access_token": token})
    post_id = pdata.get("id")
    if post_id:
        return {"ok": True, "post_id": post_id,
                "creation_id": creation_id}
    return {"ok": False,
            "error": f"Graph API refused to publish: {pdata}"}


def instagram_publish(image_url, caption, token=None,
                      ig_user_id=None):
    """Publish a photo post. Real work or honest failure — never
    raises. Local paths are refused before any network call."""
    token, ig_user_id = _ig_creds(token, ig_user_id)
    image_url = (image_url or "").strip()
    if not _looks_public_url(image_url):
        return {"ok": False, "skipped": True,
                "reason": (
                    "refused: image_url must be a PUBLIC https URL "
                    f"— got {image_url!r}. Instagram's servers "
                    "fetch the image themselves, so a local file "
                    "path can never work. Upload the image "
                    "somewhere public first, then pass that URL.")}
    if not token or not ig_user_id:
        return {"ok": False, "skipped": True,
                "reason": ("IG_ACCESS_TOKEN / IG_USER_ID not set — "
                           "publish skipped, nothing was sent")}
    try:
        _code, data = _http_json(
            f"{_IG_API}/{ig_user_id}/media",
            payload={"image_url": image_url, "caption": caption,
                     "access_token": token})
        creation_id = data.get("id")
        if not creation_id:
            return {"ok": False,
                    "error": (f"Graph API refused the media "
                              f"container: {data}")}
        return _ig_publish_container(ig_user_id, creation_id, token)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def instagram_publish_reel(video_url, caption, token=None,
                           ig_user_id=None):
    """Publish a Reel from a PUBLIC video URL (Graph API media
    container with media_type=REELS). Same honest contract as the
    photo flow; local paths are refused before any network call."""
    token, ig_user_id = _ig_creds(token, ig_user_id)
    video_url = (video_url or "").strip()
    if not _looks_public_url(video_url):
        return {"ok": False, "skipped": True,
                "reason": (
                    "refused: video_url must be a PUBLIC https URL "
                    f"— got {video_url!r}. Meta's servers fetch "
                    "the video themselves. Upload it somewhere "
                    "public first, then pass that URL.")}
    if not token or not ig_user_id:
        return {"ok": False, "skipped": True,
                "reason": ("IG_ACCESS_TOKEN / IG_USER_ID not set — "
                           "publish skipped, nothing was sent")}
    try:
        _code, data = _http_json(
            f"{_IG_API}/{ig_user_id}/media",
            payload={"media_type": "REELS", "video_url": video_url,
                     "caption": caption, "access_token": token})
        creation_id = data.get("id")
        if not creation_id:
            return {"ok": False,
                    "error": (f"Graph API refused the Reels "
                              f"container: {data}")}
        return _ig_publish_container(ig_user_id, creation_id, token)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ==================================================================
# 4. WHATSAPP — honest one-tap package builder
# ==================================================================

_WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDkc9g6WaKg0owHJE3B"


def whatsapp_build_package(text, out_path, title=""):
    """Build the ready-to-paste WhatsApp channel package file.

    HONEST BY DESIGN: there is no WhatsApp Business API for this
    channel — Cyrus posts with one tap on his phone. This function
    writes the package and reports automated=False. It NEVER
    claims anything was posted.
    """
    lines = [
        f"# WhatsApp package — {title or 'Cyrus Team post'}",
        "",
        f"Channel: {_WHATSAPP_CHANNEL_URL}",
        "How: copy the text below into the channel (one tap by "
        "Cyrus). Nothing is auto-posted — no WhatsApp Business API "
        "is configured for this channel.",
        "",
        "---- COPY FROM HERE ----",
        text,
        "---- TO HERE ----",
        "",
    ]
    directory = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(directory, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"ok": True, "path": out_path, "automated": False,
            "note": ("package ready for Cyrus's one tap — NOT "
                     "posted (no WhatsApp Business API)")}


# ==================================================================
# 4b. TIKTOK — manual one-tap cross-post package (distribution-only)
#
# Cyrus's decision (2026-10-27): TikTok is REOPENED as a
# distribution channel only — no API, no auto-post, no separate
# growth work. The daily package's vertical render is cross-posted
# by Cyrus from his phone (@cyrusoutdoor). 2-week data test; dead
# numbers after ~2 weeks of daily posts close it again
# (VIRAL-PROTOCOL.md).
# ==================================================================

_TIKTOK_URL = "https://www.tiktok.com/@cyrusoutdoor"


def tiktok_build_package(video_path, caption, hashtags,
                         cover_text, out_path, title=""):
    """Build the ready-to-post TikTok package file for one video.

    HONEST BY DESIGN: no TikTok API exists for this team — Cyrus
    posts with one tap on his phone. This writes the package
    (video reference + TikTok-native caption + hashtag set +
    on-screen cover text line) and reports automated=False. It
    NEVER claims anything was posted. The package as a whole
    stays behind the same approval gate as every other channel.
    """
    tags = " ".join(
        "#" + str(h).strip().lstrip("#")
        for h in (hashtags or []) if str(h).strip())
    lines = [
        f"# TikTok package — {title or 'Cyrus AI daily video'}",
        "",
        "Channel: Cyrus Outdoors (@cyrusoutdoor) — "
        f"{_TIKTOK_URL}",
        "How: Cyrus posts the video below from his phone (one "
        "tap). Nothing is auto-posted — no TikTok API is "
        "configured for this team. Distribution-only channel "
        "(2-week data test, opened 2026-10-27).",
        "",
        f"VIDEO FILE: {video_path}",
        f"COVER TEXT (on-screen, first frame): {cover_text}",
        "",
        "---- CAPTION (copy into TikTok) ----",
        caption or "",
        "",
        "---- HASHTAGS ----",
        tags,
        "",
    ]
    directory = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(directory, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"ok": True, "path": out_path, "automated": False,
            "note": ("TikTok package ready for Cyrus's one tap "
                     "— NOT posted (no TikTok API); "
                     "distribution-only 2-week test channel")}


# ==================================================================
# 5. RENDER HANDLING — run the Director's engine for a package
# ==================================================================

def render_package_video(package, out_path, bank=None,
                         target_seconds=30, music_path=None,
                         workdir=None):
    """Render a package's video end to end.

    DEFAULT (bank=None): the Zero-Waste render — topic-matched
    stock footage under the pre-render semantic check, beat-
    synced voice, ffmpeg render (see render_topic_package_video).
    The topic-blind personal-bank fill that produced Critical
    Failure #001 is retired as a default.

    When a FootageBank is passed EXPLICITLY, the legacy bank path
    below runs (kept for proofs/fixtures that deliberately
    exercise the bank): footage plan (no looping) -> Piper voice
    -> ffmpeg render -> ffprobe verification (inside
    director.render).

    Every stage's real result is recorded on the package. A stage
    that cannot run returns its honest failure ("stage" named) —
    the package is never marked as having a video it doesn't have.
    PiperNotConfiguredError propagates loudly by design.
    """
    if bank is None:
        return render_topic_package_video(
            package, out_path, target_seconds=target_seconds,
            workdir=workdir, music_path=music_path)
    script = (package or {}).get("script") or {}
    spoken = (script.get("script") or "").strip()
    if not spoken:
        return {"ok": False, "stage": "script",
                "error": "package has no spoken script to voice"}
    bank = bank or director_agent.FootageBank()
    if not bank.clips:
        scanned = bank.scan()
        if not scanned.get("ok"):
            return {"ok": False, "stage": "footage",
                    "error": scanned.get("error")}
    try:
        plan = bank.plan(target_seconds)
    except director_agent.InsufficientFootageError as e:
        return {"ok": False, "stage": "footage", "error": str(e)}
    workdir = workdir or os.path.dirname(os.path.abspath(out_path))
    os.makedirs(workdir, exist_ok=True)
    voice_path = os.path.join(workdir, "voice.wav")
    voice = director_agent.synthesize(spoken, voice_path)
    if not voice.get("ok"):
        return {"ok": False, "stage": "voice", "error": voice}
    rendered = director_agent.render(
        plan, out_path, voice_wav=voice["path"],
        music_path=music_path)
    if not rendered.get("ok"):
        return {"ok": False, "stage": "render", "error": rendered}
    package["video_path"] = rendered["path"]
    package["render"] = rendered
    package["voice"] = voice
    log.info("package video rendered: %s (%.2fs)",
             rendered["path"], rendered["duration_s"])
    return {"ok": True, "video": rendered, "voice": voice,
            "plan": plan}


# ==================================================================
# 5b. TOPIC-MATCHED STOCK FOOTAGE — Zero-Waste Protocol sourcing
#
# Gate order is law (cheap first, credit last):
#   (a) FREE metadata gate — no API, no download, no vision call;
#   (b) download survivors -> ffprobe;
#   (c) per-clip VISION verification (qa_agent.clip_visual_check);
#   (d) beat-synced render.
# A clip that fails any gate is rejected with its stage and
# reason recorded in the footage manifest. STOPs are appended
# to smart_agents/ERROR-LOG.md. When the accepted pool cannot
# cover the target duration the flow STOPS — honestly, in the
# open — instead of filling with off-topic footage.
# ==================================================================

STOCK_PER_QUERY = 6
STOCK_MAX_CANDIDATES = 30
STOCK_MAX_DOWNLOAD_BYTES = 180 * 1024 * 1024

BEAT_WINDOWS_S = {"hook_0_3": 3.0, "tension_3_15": 12.0,
                  "climax_15_25": 10.0, "loop_cta_25_30": 5.0}
BEAT_ORDER = tuple(BEAT_WINDOWS_S)
VOICE_MAX_LENGTH_SCALE = 1.4

# Content class the metadata gate STOPs on sight when the topic
# is urban/city travel (Cyrus's stop rule, Zero-Waste Protocol).
NATURE_CLASS_WORDS = (
    "nature", "forest", "wildlife", "animal", "animals",
    "whale", "whales", "orca", "orcas", "dolphin", "dolphins",
    "shark", "sharks", "underwater", "ocean", "bird", "birds",
    "bear", "bears", "deer", "elk", "moose", "wolf", "wolves",
    "fox", "squirrel", "monkey", "elephant", "lion", "tiger",
    "penguin", "turtle", "frog", "snake", "butterfly",
    "coral", "reef", "waterfall", "glacier", "jungle",
    "savanna", "volcano", "aurora",
)
_URBAN_MARKERS = (
    "city", "urban", "downtown", "strip", "skyline", "casino",
    "hotel", "hotels", "nightlife", "street", "streets",
    "boulevard", "las vegas", "new york", "los angeles",
    "chicago", "miami", "seattle", "toronto", "vancouver",
    "san francisco", "houston", "dallas", "boston",
)
_NATURE_MARKERS = (
    "canyon", "waterfall", "forest", "national park", "wildlife",
    "hiking", "trail", "mountain", "lake", "river gorge",
)
_META_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "with", "for", "is", "are", "your", "you", "it", "its",
    "that", "this", "video", "footage", "stock", "clip",
}


def _class_markers(text, markers):
    low = f" {text.lower()} "
    return [m for m in markers
            if re.search(rf"[\s\W]{re.escape(m)}[\s\W]", low)]


def _topic_terms(topic, queries):
    """Keyword terms for the metadata gate: full phrases plus
    content words (len >= 3, no stopwords)."""
    phrases = []
    words = set()
    for text in [topic or ""] + list(queries or []):
        text = (text or "").strip()
        if not text:
            continue
        if len(text) >= 5:
            phrases.append(text.lower())
        for w in re.findall(r"[a-z0-9']+", text.lower()):
            if len(w) >= 3 and w not in _META_STOPWORDS:
                words.add(w)
    return phrases, words


def metadata_gate_check(meta_text, topic, queries, topic_class=""):
    """THE FREE PRE-RENDER SEMANTIC GATE (pure — no API, no
    download, no vision call; unit-testable).

    A candidate is admitted only when its own metadata (title /
    description / tags) carries at least one topic term, AND —
    when the topic class is urban — carries NO nature-class
    term. Every admitted clip has matched: the match rate of
    admitted footage is 100% by construction.

    Returns {"passed", "stopped", "matched_terms", "class_hits",
             "reason"}.
    """
    blob = f" {(meta_text or '').lower()} "
    phrases, words = _topic_terms(topic, queries)
    matched = [p for p in phrases if p in blob]
    matched += [w for w in sorted(words)
                if re.search(rf"[\s\W]{re.escape(w)}[\s\W]", blob)]
    class_hits = []
    if (topic_class or "").lower() == "urban":
        class_hits = [w for w in NATURE_CLASS_WORDS
                      if re.search(rf"[\s\W]{re.escape(w)}[\s\W]",
                                   blob)]
    if class_hits:
        return {"passed": False, "stopped": True,
                "matched_terms": matched, "class_hits": class_hits,
                "reason": (f"STOP: metadata content class "
                           f"{class_hits} contradicts the urban "
                           f"topic {topic!r} (Zero-Waste stop "
                           "rule)")}
    if not matched:
        return {"passed": False, "stopped": False,
                "matched_terms": [], "class_hits": [],
                "reason": ("metadata carries none of the script's "
                           "topic terms — not admitted")}
    return {"passed": True, "stopped": False,
            "matched_terms": matched, "class_hits": [],
            "reason": f"metadata matches topic terms: {matched}"}


def derive_footage_keywords(script, idea=None):
    """Derive (topic, topic_class, stock search queries) from a
    script package. The thinking tier writes concrete visual
    search phrases; a deterministic fallback uses title/hook when
    the AI is unavailable. Returns {"topic", "topic_class",
    "queries", "ai_used"}."""
    script = script or {}
    title = ((idea or {}).get("title") or script.get("title")
             or "").strip()
    prompt = (
        "A short travel video needs stock footage that MATCHES "
        "its script exactly.\n"
        f"title: {title}\n"
        f"hook: {script.get('hook', '')}\n"
        f"spoken script: {script.get('script', '')}\n\n"
        "Reply ONLY valid JSON: {\"topic\": \"the place/subject "
        "in a few words\", \"topic_class\": \"urban\" | \"nature\" "
        "| \"mixed\", \"visual_world\": \"one sentence describing "
        "what ON-TOPIC footage LOOKS like — the place itself and "
        "its iconic visual elements (this sentence is the "
        "anchor the footage is judged against)\", \"queries\": "
        "[4-6 SHORT stock-library search phrases of 2-4 words "
        "each — stock engines match short phrases. The FIRST "
        "queries must cover the PLACE ITSELF and its iconic "
        "elements (location name + landmarks / streets / night "
        "/ aerial terms, e.g. \"Las Vegas Strip night\", \"Las "
        "Vegas casino\", \"Las Vegas aerial\"); only then add "
        "phrases for the script's specific subjects]}"
    )
    data, ok = common.ask_json(
        prompt,
        "You are a stock-footage researcher for a travel video "
        "team. Your search phrases decide what the audience "
        "SEES; they must match the script's world exactly.",
        role="thinking", max_tokens=400, temperature=0.3)
    if ok and data and data.get("queries"):
        queries = [str(q).strip() for q in data["queries"]
                   if str(q).strip()][:6]
        topic = str(data.get("topic") or title).strip()
        tclass = str(data.get("topic_class") or "").strip().lower()
        if tclass not in ("urban", "nature", "mixed"):
            tclass = ""
        if queries and topic:
            if not tclass:
                tclass = _fallback_topic_class(topic, queries)
            world = str(data.get("visual_world") or "").strip()
            return {"topic": topic, "topic_class": tclass,
                    "queries": queries, "ai_used": True,
                    "visual_world": world}
    topic = title or (script.get("hook") or "").strip()
    queries = []
    for cand in (title, script.get("hook") or "",
                 f"{title} footage" if title else ""):
        cand = (cand or "").strip()
        if cand and cand not in queries:
            queries.append(cand)
    return {"topic": topic,
            "topic_class": _fallback_topic_class(topic, queries),
            "queries": queries, "ai_used": False,
            "visual_world": ""}


def _fallback_topic_class(topic, queries):
    blob = " ".join([topic or ""] + list(queries or []))
    if _class_markers(blob, _URBAN_MARKERS):
        return "urban"
    if _class_markers(blob, _NATURE_MARKERS):
        return "nature"
    return "mixed"


# ------------------------------------------------------------------
# Stock sources — tried in the standing order. Every source
# returns candidate dicts: {title, meta_text, page_url,
# download_url, source, license, width, height, size_bytes,
# needs_derivative}. Failures raise; the aggregator records them.
# ------------------------------------------------------------------

def _strip_html(text):
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _commons_candidates(query, limit=STOCK_PER_QUERY):
    _status, data = _http_json(
        "https://commons.wikimedia.org/w/api.php",
        params={"action": "query", "format": "json",
                "generator": "search",
                "gsrsearch": f"{query} filetype:video",
                "gsrnamespace": 6, "gsrlimit": limit,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata"},
        timeout=30)
    out = []
    for page in (data.get("query") or {}).get("pages", {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        if not ii.get("url"):
            continue
        em = ii.get("extmetadata") or {}
        lic = ((em.get("LicenseShortName") or {}).get("value")
               or "see Commons file page")
        desc = _strip_html(
            (em.get("ImageDescription") or {}).get("value") or "")
        out.append({
            "title": page.get("title", ""),
            "meta_text": f"{page.get('title', '')} {desc}",
            "page_url": ii.get("descriptionurl") or "",
            "download_url": ii["url"],
            "source": "wikimedia_commons", "license": lic,
            "width": ii.get("width"), "height": ii.get("height"),
            "size_bytes": ii.get("size"),
            "needs_derivative": True,
        })
    return out


_COMMONS_DERIV_PREFS = ("2160p.vp9.webm", "1440p.vp9.webm",
                        "1080p.vp9.webm", "1080p.webm",
                        "720p.vp9.webm", "720p.webm",
                        "480p.vp9.webm", "480p.webm",
                        "360p.vp9.webm")


def _head(url, timeout=15):
    req = urllib.request.Request(url, method="HEAD",
                                 headers=dict(_UA))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        length = resp.headers.get("Content-Length")
        return resp.status, (int(length) if length else None)


def _commons_derivative(orig_url):
    """Resolve a transcoded (smaller) derivative of a Commons
    video by HEAD-probing the known transcoded URL pattern.
    Returns (url, size_bytes|None) or (None, None)."""
    # The API's url field may carry tracking query params —
    # parse the bare path (hash dirs are 1 + 2 hex chars).
    path = urllib.parse.urlparse(orig_url or "").path
    m = re.match(
        r"(/wikipedia/commons)/([0-9a-f])/([0-9a-f]{2})/(.+)$",
        path)
    if not m:
        return None, None
    _commons, h1, h2, fname = m.groups()
    base = "https://upload.wikimedia.org/wikipedia/commons"
    found = []
    for suffix in _COMMONS_DERIV_PREFS:
        url = (f"{base}/transcoded/{h1}/{h2}/{fname}/"
               f"{fname}.{suffix}")
        try:
            status, length = _head(url)
        except Exception:
            continue
        if status == 200:
            found.append((suffix, url, length))
    for suffix, url, length in found:
        if length is None or length <= STOCK_MAX_DOWNLOAD_BYTES:
            return url, length
    if found:
        smallest = min(found,
                       key=lambda t: t[2] if t[2] is not None
                       else 1 << 62)
        if (smallest[2] is not None
                and smallest[2] <= STOCK_MAX_DOWNLOAD_BYTES):
            return smallest[1], smallest[2]
    return None, None


def _archive_candidates(query, limit=STOCK_PER_QUERY):
    qs = urllib.parse.urlencode(
        [("q", f"({query}) AND mediatype:movies"),
         ("fl", "identifier"), ("fl", "title"),
         ("rows", limit), ("output", "json")], doseq=True)
    req = urllib.request.Request(
        f"https://archive.org/advancedsearch.php?{qs}",
        headers=dict(_UA))
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for doc in (data.get("response") or {}).get("docs") or []:
        ident = doc.get("identifier")
        if not ident:
            continue
        try:
            _s, meta = _http_json(
                f"https://archive.org/metadata/{ident}",
                timeout=30)
        except Exception:
            continue
        md = meta.get("metadata") or {}
        best = None
        for f in meta.get("files") or []:
            name = f.get("name") or ""
            if not name.lower().endswith(".mp4"):
                continue
            try:
                size = int(f.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            if size and size > STOCK_MAX_DOWNLOAD_BYTES:
                continue
            if (best is None
                    or (f.get("width") or 0) > (best.get("width")
                                                or 0)):
                best = f
        if not best:
            continue
        lic = (md.get("licenseurl") or md.get("license")
               or "not stated in item metadata")
        subjects = md.get("subject") or ""
        if isinstance(subjects, list):
            subjects = " ".join(str(s) for s in subjects)
        out.append({
            "title": doc.get("title") or ident,
            "meta_text": (f"{doc.get('title') or ''} "
                          f"{md.get('description') or ''} "
                          f"{subjects}"),
            "page_url": f"https://archive.org/details/{ident}",
            "download_url": (
                f"https://archive.org/download/{ident}/"
                + urllib.parse.quote(best["name"])),
            "source": "archive_org", "license": str(lic),
            "width": best.get("width"),
            "height": best.get("height"),
            "size_bytes": int(best.get("size") or 0) or None,
            "needs_derivative": False,
        })
    return out


def _openverse_candidates(query, limit=STOCK_PER_QUERY):
    _status, data = _http_json(
        "https://api.openverse.org/v1/videos/",
        params={"q": query, "page_size": limit}, timeout=30)
    out = []
    for r in data.get("results") or []:
        if not r.get("url"):
            continue
        tags = " ".join(
            str(t.get("name") if isinstance(t, dict) else t)
            for t in (r.get("tags") or []))
        out.append({
            "title": r.get("title") or "",
            "meta_text": f"{r.get('title') or ''} {tags}",
            "page_url": r.get("foreign_landing_url") or "",
            "download_url": r["url"],
            "source": "openverse",
            "license": str(r.get("license") or "see source page"),
            "width": r.get("width"), "height": r.get("height"),
            "size_bytes": None, "needs_derivative": False,
        })
    return out


def _pexels_candidates(query, limit=STOCK_PER_QUERY):
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if not key:
        return []
    req = urllib.request.Request(
        "https://api.pexels.com/videos/search?"
        + urllib.parse.urlencode({"query": query,
                                  "per_page": limit}),
        headers={"Authorization": key, **_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for v in data.get("videos") or []:
        files = [f for f in v.get("video_files") or []
                 if f.get("link")]
        if not files:
            continue
        best = max(files, key=lambda f: f.get("width") or 0)
        out.append({
            "title": v.get("url", ""),
            "meta_text": v.get("url", ""),
            "page_url": v.get("url") or "",
            "download_url": best["link"],
            "source": "pexels", "license": "Pexels License",
            "width": best.get("width"),
            "height": best.get("height"),
            "size_bytes": None, "needs_derivative": False,
        })
    return out


def _pixabay_candidates(query, limit=STOCK_PER_QUERY):
    key = (os.environ.get("PIXABAY_API_KEY") or "").strip()
    if not key:
        return []
    _status, data = _http_json(
        "https://pixabay.com/api/videos/",
        params={"key": key, "q": query, "per_page": limit},
        timeout=30)
    out = []
    for hit in data.get("hits") or []:
        videos = hit.get("videos") or {}
        best = (videos.get("large") or videos.get("medium")
                or videos.get("small") or {})
        if not best.get("url"):
            continue
        out.append({
            "title": hit.get("pageurl", ""),
            "meta_text": f"{hit.get('tags', '')}",
            "page_url": hit.get("pageurl") or "",
            "download_url": best["url"],
            "source": "pixabay",
            "license": "Pixabay Content License",
            "width": best.get("width"),
            "height": best.get("height"),
            "size_bytes": best.get("size"),
            "needs_derivative": False,
        })
    return out


def _stock_sources():
    """The standing source order. Key-gated sources report
    themselves skipped when no key exists — never an error."""
    sources = []
    for name, fn in (("pexels", _pexels_candidates),
                     ("pixabay", _pixabay_candidates)):
        keyed = bool((os.environ.get(
            "PEXELS_API_KEY" if name == "pexels"
            else "PIXABAY_API_KEY") or "").strip())
        sources.append((name, fn, keyed))
    sources += [("wikimedia_commons", _commons_candidates, True),
                ("openverse", _openverse_candidates, True),
                ("archive_org", _archive_candidates, True)]
    return sources


def search_stock_footage(queries, per_query=STOCK_PER_QUERY):
    """Search every source for every query, in the standing
    order. Returns {"candidates": [...], "attempts": [...]}.
    Never raises — a source failure is recorded in attempts,
    not hidden. Candidates are deduped by download URL."""
    candidates, attempts, seen = [], [], set()
    for query in queries or []:
        for name, fn, keyed in _stock_sources():
            if not keyed:
                attempts.append({"query": query, "source": name,
                                 "result": "skipped — no API key "
                                           "in env"})
                continue
            try:
                found = fn(query, limit=per_query)
            except Exception as e:
                attempts.append({"query": query, "source": name,
                                 "result": f"error: "
                                           f"{type(e).__name__}: "
                                           f"{e}"})
                continue
            attempts.append({"query": query, "source": name,
                             "result": f"{len(found)} candidates"})
            for cand in found:
                url = cand.get("download_url")
                if not url or url in seen:
                    continue
                seen.add(url)
                cand = dict(cand)
                cand["query"] = query
                candidates.append(cand)
                if len(candidates) >= STOCK_MAX_CANDIDATES:
                    return {"candidates": candidates,
                            "attempts": attempts}
    return {"candidates": candidates, "attempts": attempts}


def _download_file(url, dest, max_bytes=STOCK_MAX_DOWNLOAD_BYTES,
                   timeout=300):
    """Stream a download with a hard size cap.
    Returns {"ok", "bytes"|"error"}."""
    req = urllib.request.Request(url, headers=dict(_UA))
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, \
                open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    os.remove(dest)
                    return {"ok": False,
                            "error": f"download exceeded "
                                     f"{max_bytes} bytes — "
                                     "aborted"}
                f.write(chunk)
    except Exception as e:
        return {"ok": False,
                "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "bytes": total}


def source_topic_footage(script, idea, dest_dir,
                         target_seconds=30, screen_clips=True,
                         pool_seconds=None):
    """The Zero-Waste sourcing flow for one package.

    keyword derivation -> stock search -> (a) metadata gate ->
    download -> probe -> (b) vision screening -> coverage
    check. Writes footage_manifest.json into dest_dir (every
    candidate's source URL, matched query, license and gate
    verdicts). Returns {"ok", "topic", "topic_class", "queries",
    "clips", "accepted_seconds", "manifest_path", "attempts"}
    or {"ok": False, "stage": "footage", "error", ...} when the
    accepted pool cannot cover the target — the hard STOP.
    """
    kw = derive_footage_keywords(script, idea)
    topic, queries = kw["topic"], kw["queries"]
    topic_class = kw["topic_class"]
    visual_world = kw.get("visual_world") or topic
    os.makedirs(dest_dir, exist_ok=True)
    found = search_stock_footage(queries)
    if not found["candidates"]:
        # Stock engines match SHORT phrases; long descriptive
        # queries can return nothing anywhere. Broaden once —
        # the metadata and vision gates still filter every
        # candidate, so a broader net admits nothing off-topic.
        broad = []
        for q in queries:
            words = q.split()
            for n in (3, 2):
                if len(words) > n:
                    cand = " ".join(words[:n])
                    if cand not in broad and cand not in queries:
                        broad.append(cand)
        if broad:
            log.info("no candidates for %r — broadening queries: "
                     "%s", topic, broad)
            found = search_stock_footage(broad)
            queries = queries + broad

    checker = None
    if screen_clips:
        from smart_agents import qa_agent as _qa

        checker = _qa.clip_visual_check

    accepted, rejected, stops = [], [], []
    total = 0.0
    worklist = list(found["candidates"])
    searched = list(queries)
    broadened = False
    idx = 0
    while idx < len(worklist):
        cand = worklist[idx]
        idx += 1
        entry = {"title": cand.get("title"),
                 "source": cand.get("source"),
                 "source_url": cand.get("page_url"),
                 "download_url": cand.get("download_url"),
                 "query": cand.get("query"),
                 "license": cand.get("license")}
        # (a) the FREE metadata gate — before any download.
        # Terms come from every query searched so far, plus the
        # query this very candidate matched.
        gate = metadata_gate_check(
            cand.get("meta_text", ""), topic,
            searched + [cand.get("query") or ""],
            topic_class=topic_class)
        entry["metadata_gate"] = gate
        if not gate["passed"]:
            entry["stage"] = "metadata_gate"
            entry["reason"] = gate["reason"]
            rejected.append(entry)
            if gate.get("stopped"):
                stops.append(entry)
            continue
        dl_url = cand["download_url"]
        if cand.get("needs_derivative"):
            deriv, _dlen = _commons_derivative(dl_url)
            if deriv:
                dl_url = deriv
            elif ((cand.get("size_bytes") or 0)
                    > STOCK_MAX_DOWNLOAD_BYTES):
                entry["stage"] = "download"
                entry["reason"] = ("original file too large and "
                                    "no transcode available")
                rejected.append(entry)
                continue
        ext = os.path.splitext(
            urllib.parse.urlparse(dl_url).path)[1] or ".mp4"
        local = os.path.join(
            dest_dir,
            f"clip_{len(accepted) + len(rejected) + 1:02d}{ext}")
        got = _download_file(dl_url, local)
        if not got.get("ok"):
            entry["stage"] = "download"
            entry["reason"] = got.get("error")
            rejected.append(entry)
            continue
        info = director_agent.probe_clip(local)
        if not info or info.get("duration_s", 0) <= 0:
            entry["stage"] = "probe"
            entry["reason"] = "ffprobe could not read the file"
            rejected.append(entry)
            continue
        # LAW 3 SELECTION GATE (Forever Protocol v2 — real &
        # cinematic quality): the footage's NATIVE resolution
        # must fill the 1080x1920 vertical frame cleanly
        # (crop factor <= 1.05 — no meaningful upscale).
        # Upscaled/blurry stock is rejected here, at selection,
        # before any vision credit is spent on it.
        native_w = cand.get("width") or info.get("width") or 0
        native_h = cand.get("height") or info.get("height") or 0
        if native_w and native_h:
            factor = max(1080.0 / native_w, 1920.0 / native_h)
            entry["native_width"] = native_w
            entry["native_height"] = native_h
            entry["crop_factor"] = round(factor, 3)
            if factor > 1.05:
                entry["stage"] = "resolution"
                entry["reason"] = (
                    f"native {native_w}x{native_h} needs a "
                    f"{factor:.2f}x upscale to fill 1080x1920 — "
                    "rejected at selection (Forever Protocol "
                    "v2, Law 3)")
                rejected.append(entry)
                continue
        entry.update({"id": os.path.splitext(
            os.path.basename(local))[0], "path": local,
            "downloaded_url": dl_url, **info})
        # (b) vision screening — after the free gate, before any
        # render. An abstention never admits a clip.
        if checker:
            verdict = checker(local, topic,
                              queries + [cand.get("query") or ""],
                              world=visual_world)
            entry["visual_check"] = {
                "ran": verdict.get("ran"),
                "on_topic": verdict.get("on_topic"),
                "frames": verdict.get("frames"),
                "note": verdict.get("note")}
            if not verdict.get("ran"):
                entry["stage"] = "visual"
                entry["reason"] = ("vision screening unavailable "
                                   "— clip not admitted: "
                                   + (verdict.get("note") or ""))
                rejected.append(entry)
                continue
            if not verdict.get("on_topic"):
                entry["stage"] = "visual"
                entry["reason"] = ("vision screening: off-topic "
                                   "for " + topic + " — "
                                   + (verdict.get("note") or ""))
                rejected.append(entry)
                continue
        accepted.append(entry)
        total = round(total + info["duration_s"], 3)
        # Coverage is judged against target_seconds, but the
        # pool keeps gathering until pool_seconds so the
        # beat-aligned planner has distinct clips per window.
        if total >= (pool_seconds or target_seconds):
            break
        # Pool exhausted short of coverage: broaden the search
        # ONCE with shorter place phrases. The gates are not
        # relaxed — every new candidate passes the same
        # metadata and vision checks.
        if idx >= len(worklist) and total < target_seconds \
                and not broadened:
            broadened = True
            extra = []
            for q in searched:
                words = q.split()
                for n in (3, 2):
                    if len(words) > n:
                        short = " ".join(words[:n])
                        if short not in extra \
                                and short not in searched:
                            extra.append(short)
            if extra:
                log.info("coverage short for %r (%.1fs) — "
                         "broadening search: %s",
                         topic, total, extra)
                more = search_stock_footage(extra)
                found["attempts"].extend(more["attempts"])
                searched.extend(extra)
                worklist.extend(more["candidates"])

    manifest = {
        "topic": topic, "topic_class": topic_class,
        "visual_world": visual_world,
        "queries": queries, "keyword_ai_used": kw["ai_used"],
        "target_seconds": target_seconds,
        "attempts": found["attempts"],
        "accepted": accepted, "rejected": rejected,
        "accepted_seconds": total,
        "generated_at": datetime.now().isoformat(),
    }
    manifest_path = os.path.join(dest_dir, "footage_manifest.json")
    if stops:
        common.append_error_log(
            "Pre-render STOP (metadata gate)",
            f"topic {topic!r}: {len(stops)} candidate clip(s) "
            "STOPPED by the free metadata gate with zero further "
            "spend (Zero-Waste Protocol)",
            "stopped: " + "; ".join(
                f"{s.get('title')} [{s.get('source')}] — "
                f"{s.get('reason')}" for s in stops))
    if total < target_seconds:
        manifest["stop_reason"] = (
            f"topic-matched footage covers only {total}s of the "
            f"{target_seconds}s target for {topic!r}")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        common.append_error_log(
            "Footage STOP (coverage)",
            manifest["stop_reason"] + " — package STOPPED "
            "instead of filling with off-topic clips",
            f"manifest: {manifest_path}")
        return {"ok": False, "stage": "footage",
                "error": manifest["stop_reason"]
                + " — stopping honestly instead of filling "
                  "with off-topic clips",
                "topic": topic, "queries": queries,
                "manifest_path": manifest_path,
                "accepted_seconds": total}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log.info("topic footage sourced for %r: %d clips, %.1fs",
             topic, len(accepted), total)
    return {"ok": True, "topic": topic,
            "topic_class": topic_class, "queries": queries,
            "visual_world": visual_world,
            "clips": accepted, "accepted_seconds": total,
            "manifest_path": manifest_path,
            "attempts": found["attempts"]}


# ------------------------------------------------------------------
# Beat-synced voice + render (Zero-Waste Protocol step c)
# ------------------------------------------------------------------

def _normalize_peak(wav_path, target_db=-1.0):
    """Peak-normalize a voice WAV to `target_db` dBFS when it
    peaks hotter. Piper synthesis + beat fitting can land the
    concatenated voice at 0.0 dBFS — true clipping, which hard
    gate Q4 (Forever Protocol v2) rightly rejects. Normalizing
    at build time makes the voice clean by construction, with
    headroom for the render's AAC encode. Best-effort: any
    failure leaves the file untouched and QA measures what is
    actually there."""
    try:
        probe = subprocess.run(
            ["ffmpeg", "-i", wav_path, "-map", "0:a:0",
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, timeout=120)
        peak = None
        for line in probe.stderr.decode(
                "utf-8", "replace").splitlines():
            if "max_volume:" in line:
                try:
                    peak = float(line.split("max_volume:")[1]
                                 .split("dB")[0].strip())
                except (IndexError, ValueError):
                    pass
        if peak is None or peak <= target_db:
            return
        gain = round(target_db - peak, 2)
        tmp_path = wav_path + ".norm.wav"
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-af",
             f"volume={gain}dB", "-c:a", "pcm_s16le", tmp_path],
            capture_output=True, timeout=120)
        if proc.returncode == 0 and os.path.isfile(tmp_path):
            os.replace(tmp_path, wav_path)
            log.info("voice peak normalized: %.1f dB -> %.1f dB",
                     peak, target_db)
    except Exception as e:
        log.warning("peak normalization skipped for %s: %s",
                    wav_path, e)


def build_beat_voice(script, workdir):
    """Synthesize the voice BEAT BY BEAT, each beat fitted to
    its golden-formula window (moderate Piper stretch, then a
    silence pad), and concatenate into one voice track — so the
    scene cuts can land exactly on the voice beat boundaries
    (measured and recorded as evidence under hard gate Q1).

    Returns {"ok", "path", "beats": [{"key", "target_s",
    "speech_s", "scale", "fitted_s"}], "boundaries_s",
    "duration_s"} or {"ok": False, "stage": "voice", "error"}.
    Scripts without beats get a single whole-script synthesis
    and empty boundaries (sync then honestly reads untested).
    PiperNotConfiguredError propagates loudly, as everywhere.
    """
    beats = (script or {}).get("beats") or {}
    spoken = ((script or {}).get("script") or "").strip()
    os.makedirs(workdir, exist_ok=True)
    whole_path = os.path.join(workdir, "voice.wav")
    if not all(str(beats.get(k) or "").strip() for k in BEAT_ORDER):
        if not spoken:
            return {"ok": False, "stage": "voice",
                    "error": "package has no spoken script"}
        voice = director_agent.synthesize(spoken, whole_path)
        if not voice.get("ok"):
            return {"ok": False, "stage": "voice", "error": voice}
        _normalize_peak(whole_path)
        return {"ok": True, "path": whole_path,
                "beats": [], "boundaries_s": [],
                "duration_s": voice.get("duration_s")}

    beat_files, beat_info, boundaries = [], [], []
    elapsed = 0.0
    for key in BEAT_ORDER:
        text = str(beats[key]).strip()
        target = BEAT_WINDOWS_S[key]
        raw_path = os.path.join(workdir, f"beat_{key}.wav")
        first = director_agent.synthesize(text, raw_path)
        if not first.get("ok"):
            return {"ok": False, "stage": "voice", "error": first}
        speech = first.get("duration_s") or 0.0
        scale = 1.0
        if 0 < speech < target:
            scale = min(VOICE_MAX_LENGTH_SCALE, target / speech)
        if scale > 1.02:
            stretched = director_agent.synthesize(
                text, raw_path, length_scale=round(scale, 3))
            if stretched.get("ok"):
                speech = stretched.get("duration_s") or speech
            else:
                scale = 1.0
        fitted = max(speech, target)
        padded_path = os.path.join(workdir, f"beat_{key}_fit.wav")
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", raw_path, "-af",
             f"apad=whole_dur={fitted:.3f}",
             "-c:a", "pcm_s16le", padded_path],
            capture_output=True, timeout=120)
        if proc.returncode != 0 or not os.path.isfile(padded_path):
            return {"ok": False, "stage": "voice",
                    "error": "ffmpeg beat padding failed: "
                             + proc.stderr.decode(
                                 "utf-8", "replace")[:200]}
        beat_files.append(padded_path)
        beat_info.append({"key": key, "target_s": target,
                          "speech_s": round(speech, 3),
                          "scale": round(scale, 3),
                          "fitted_s": round(fitted, 3)})
        elapsed = round(elapsed + fitted, 3)
        boundaries.append(elapsed)
    list_path = os.path.join(workdir, "beats_concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in beat_files:
            f.write(f"file '{os.path.abspath(path)}'\n")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
         list_path, "-c:a", "pcm_s16le", whole_path],
        capture_output=True, timeout=120)
    if proc.returncode != 0 or not os.path.isfile(whole_path):
        return {"ok": False, "stage": "voice",
                "error": "ffmpeg beat concat failed: "
                         + proc.stderr.decode(
                             "utf-8", "replace")[:200]}
    total = boundaries[-1] if boundaries else 0.0
    _normalize_peak(whole_path)
    return {"ok": True, "path": whole_path, "beats": beat_info,
            "boundaries_s": boundaries[:-1], "duration_s": total}


def _materialize_subclip(src_path, start_s, dur_s, dest_path):
    """Cut one exact segment out of a source clip into its own
    file (re-encoded, no audio — the render only uses clip
    video). Returns True on success."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{start_s:.3f}", "-i",
             src_path, "-t", f"{dur_s:.3f}", "-an", "-c:v",
             "libx264", "-preset", "veryfast", "-pix_fmt",
             "yuv420p", dest_path],
            capture_output=True, timeout=300)
    except Exception:
        return False
    return (proc.returncode == 0 and os.path.isfile(dest_path)
            and os.path.getsize(dest_path) > 0)


def _aligned_plan(clips, windows_s, workdir=None):
    """Build a render plan whose segment boundaries land on the
    beat windows. Each window is filled from the accepted pool;
    materialized subclips guarantee no frame range is ever
    repeated and nothing loops.

    Every window STARTS with a genuine visual cut, so the
    scene changes land on the voice beat boundaries (the
    measurement recorded as evidence under hard gate Q1): a
    different pool clip opens the window when one is
    available; when a single long clip must carry on, its
    offset JUMPS forward to an unused stretch instead of
    flowing seamlessly across the boundary. Returns {"clips",
    "total_s", "cuts_s", "looping": False} or None when the
    pool cannot fill every window."""
    pool = [{"clip": c, "offset": 0.0} for c in (clips or [])]
    seg_dir = None
    if workdir:
        seg_dir = os.path.join(workdir, "segments")
        os.makedirs(seg_dir, exist_ok=True)
    chosen, cuts, elapsed = [], [], 0.0
    seg_no = 0
    for wi, window in enumerate(windows_s):
        remaining = round(float(window), 3)
        prev_id = chosen[-1]["id"] if chosen else None
        first_pick = True
        while remaining > 0.001:
            slots = [s for s in pool
                     if s["clip"]["duration_s"] - s["offset"]
                     > 0.05]
            if not slots:
                return None
            slot = None
            if first_pick and wi > 0 and prev_id is not None:
                slot = next(
                    (s for s in slots
                     if s["clip"]["id"] != prev_id), None)
            if slot is None:
                slot = slots[0]
                if (first_pick and wi > 0
                        and prev_id is not None
                        and slot["clip"]["id"] == prev_id):
                    jump_to = slot["offset"] + 45.0
                    if (slot["clip"]["duration_s"] - jump_to
                            >= remaining):
                        slot["offset"] = round(jump_to, 3)
            first_pick = False
            clip = slot["clip"]
            start = slot["offset"]
            seg = min(clip["duration_s"] - start, remaining)
            seg = round(seg, 3)
            path = clip["path"]
            if seg_dir:
                seg_no += 1
                dest = os.path.join(seg_dir, f"seg_{seg_no:02d}.mp4")
                if not _materialize_subclip(clip["path"], start,
                                             seg, dest):
                    log.warning("subclip failed: %s @%.2f",
                                clip["path"], start)
                    return None
                path = dest
            chosen.append({
                "id": clip["id"], "path": path,
                "segment_s": seg,
                "source_duration_s": clip["duration_s"],
                "source_offset_s": round(start, 3),
                "source": clip.get("source"),
                "source_url": clip.get("source_url"),
                "license": clip.get("license"),
                "query": clip.get("query")})
            slot["offset"] = round(start + seg, 3)
            elapsed = round(elapsed + seg, 3)
            cuts.append(elapsed)
            remaining = round(remaining - seg, 3)
    return {"clips": chosen, "total_s": elapsed,
            "cuts_s": cuts[:-1], "looping": False,
            "topic_matched": True}


def render_topic_package_video(package, out_path,
                               target_seconds=30, workdir=None,
                               music_path=None):
    """The Zero-Waste render: topic-matched sourcing (metadata
    gate -> vision) -> beat-synced voice -> a footage plan whose
    cuts land on the voice beat boundaries -> ffmpeg render.

    Records on the package: footage (manifest summary), topic,
    footage_keywords, and sync {beat_boundaries_s, plan_cuts_s,
    beats, voice_duration_s} for QA's hard gate Q3. A stage that
    cannot run returns its honest failure — the package is
    never marked as having a video it doesn't have.
    """
    script = (package or {}).get("script") or {}
    spoken = (script.get("script") or "").strip()
    if not spoken:
        return {"ok": False, "stage": "script",
                "error": "package has no spoken script to voice"}
    workdir = workdir or os.path.dirname(os.path.abspath(out_path))
    os.makedirs(workdir, exist_ok=True)
    footage_dir = os.path.join(workdir, "footage")
    sourced = source_topic_footage(
        script, (package or {}).get("idea"), footage_dir,
        target_seconds=target_seconds,
        pool_seconds=target_seconds * 3)
    if not sourced.get("ok"):
        return sourced
    voice = build_beat_voice(script, workdir)
    if not voice.get("ok"):
        return voice
    if voice.get("beats"):
        windows = [b["fitted_s"] for b in voice["beats"]]
    else:
        windows = [float(target_seconds)]
    plan = _aligned_plan(sourced["clips"], windows,
                         workdir=workdir)
    if plan is None:
        return {"ok": False, "stage": "footage",
                "error": "accepted clips cannot fill every beat "
                         "window distinctly — stopping instead "
                         "of reusing footage"}
    rendered = director_agent.render(
        plan, out_path, voice_wav=voice["path"],
        music_path=music_path)
    if not rendered.get("ok"):
        return {"ok": False, "stage": "render", "error": rendered}
    package["video_path"] = rendered["path"]
    package["render"] = rendered
    package["voice"] = {"path": voice["path"],
                         "duration_s": voice.get("duration_s"),
                         "beats": voice.get("beats")}
    package["topic"] = sourced["topic"]
    package["visual_world"] = sourced.get("visual_world")
    package["footage_keywords"] = sourced["queries"]
    package["footage"] = {
        "topic": sourced["topic"],
        "topic_class": sourced["topic_class"],
        "queries": sourced["queries"],
        "manifest_path": sourced["manifest_path"],
        "clips": [{"id": c["id"], "source": c.get("source"),
                   "source_url": c.get("source_url"),
                   "license": c.get("license"),
                   "query": c.get("query")}
                  for c in plan["clips"]],
    }
    package["sync"] = {
        "beat_boundaries_s": voice.get("boundaries_s") or [],
        "plan_cuts_s": plan["cuts_s"],
        "beats": voice.get("beats"),
        "voice_duration_s": voice.get("duration_s"),
    }
    log.info("topic video rendered: %s (%.2fs, beats synced)",
             rendered["path"], rendered["duration_s"])
    return {"ok": True, "video": rendered, "voice": voice,
            "plan": plan, "footage": sourced}


# ==================================================================
# 6. PUBLISH DISPATCHER — one entry, real per-channel results
# ==================================================================

def publish_entry(entry):
    """Publish one approved queue entry to its channels.

    entry: {"caption"/"script": {...}, "channels": [...],
            "video_path": ..., "image_public_url": ...}
    Returns {"results": {channel: result}, "any_ok": bool,
             "all_ok": bool}. Every channel result is the real
    API result (or honest skip / loud credential failure recorded
    as an error — never as a send).
    """
    script = entry.get("script") or {}
    caption = (entry.get("caption")
               or script.get("caption")
               or script.get("title") or "")
    results = {}
    for channel in entry.get("channels") or ["telegram"]:
        if channel == "telegram":
            if entry.get("video_path"):
                results[channel] = telegram_publish_file(
                    entry["video_path"], caption=caption,
                    kind="video")
            else:
                results[channel] = telegram_publish(caption)
        elif channel == "youtube":
            try:
                results[channel] = youtube_upload(
                    entry.get("video_path", ""),
                    script.get("title") or caption[:60],
                    description=script.get("description", ""),
                    tags=script.get("hashtags") or [])
            except YouTubeNotConfiguredError as e:
                results[channel] = {"ok": False, "error": str(e)}
        elif channel == "instagram":
            if entry.get("video_path") and _looks_public_url(
                    entry.get("video_public_url", "")):
                results[channel] = instagram_publish_reel(
                    entry["video_public_url"], caption)
            else:
                results[channel] = instagram_publish(
                    entry.get("image_public_url", ""), caption)
        elif channel == "whatsapp":
            results[channel] = {
                "ok": False, "skipped": True,
                "reason": ("WhatsApp is manual one-tap — build "
                           "the package with "
                           "whatsapp_build_package()")}
        elif channel == "tiktok":
            results[channel] = {
                "ok": False, "skipped": True,
                "reason": ("TikTok is manual one-tap "
                           "distribution-only — build the package "
                           "with tiktok_build_package()")}
        else:
            results[channel] = {"ok": False,
                                "error": f"unknown channel {channel!r}"}
    attempted = [r for r in results.values() if not r.get("skipped")]
    any_ok = any(r.get("ok") for r in results.values())
    all_ok = bool(attempted) and all(r.get("ok") for r in attempted)
    return {"results": results, "any_ok": any_ok, "all_ok": all_ok}


class DeveloperAgent:
    """The Core Developer as one callable agent."""

    def telegram(self, text):
        return telegram_publish(text)

    def youtube_status(self):
        return youtube_status()

    def render_package_video(self, package, out_path, **kwargs):
        return render_package_video(package, out_path, **kwargs)

    def publish(self, entry):
        return publish_entry(entry)
