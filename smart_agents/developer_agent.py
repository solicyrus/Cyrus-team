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

Credentials come ONLY from the environment / credential files
named in .env.example. Values are never printed or logged.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import uuid

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
# 5. RENDER HANDLING — run the Director's engine for a package
# ==================================================================

def render_package_video(package, out_path, bank=None,
                         target_seconds=30, music_path=None,
                         workdir=None):
    """Render a package's video end to end:
    footage plan (no looping) -> Piper voice of the script ->
    ffmpeg render -> ffprobe verification (inside director.render).

    Every stage's real result is recorded on the package. A stage
    that cannot run returns its honest failure ("stage" named) —
    the package is never marked as having a video it doesn't have.
    PiperNotConfiguredError propagates loudly by design.
    """
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
