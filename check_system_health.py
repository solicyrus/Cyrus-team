#!/usr/bin/env python3
"""CYRUS TEAM — check_system_health.py

Live activation health check. Run BEFORE the team starts work:

    python3 check_system_health.py

For every service the team uses, one line is printed:

    <service> — <OK|NOT_SET|FAILED> — <detail>

  OK      a REAL minimal authenticated call succeeded just now.
  NOT_SET the environment variable is absent. Honest "not yet" —
          a warning, never a failure.
  FAILED  the variable IS set but the real call failed (HTTP
          status / error class is shown, never the key itself).

Exit code: 0 when every CONFIGURED service is OK (not-set items
are warnings), 1 when any configured service FAILED.

INFO lines (local tools, gate state) are informational only and
never affect the exit code.

Secrets are read from the environment (the repo-root .env is
loaded via python-dotenv when available). No key value is ever
printed, logged, or stored by this script.
"""

import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

TIMEOUT = 20
_failures = []


def report(service, status, detail, counts=True):
    print(f"{service} — {status} — {detail}")
    if counts and status == "FAILED":
        _failures.append(service)


def env(name):
    return (os.environ.get(name) or "").strip()


def http_json(method, url, headers=None, form=None):
    """One small HTTP call. Returns (status, parsed_json_or_None,
    error_text). Never raises; the URL is never printed by callers
    (Telegram/Gemini URLs can carry credentials)."""
    data = None
    hdrs = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body), ""
            except Exception:
                return resp.status, None, "non-JSON response body"
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
            parsed = json.loads(body)
        except Exception:
            parsed = None
        return exc.code, parsed, f"HTTP {exc.code}"
    except Exception as exc:  # DNS, timeout, TLS, ...
        return None, None, f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------------
# Service checks
# ------------------------------------------------------------------

def check_openai():
    key = env("OPENAI_API_KEY")
    if not key:
        report("OpenAI (team brain)", "NOT_SET",
               "OPENAI_API_KEY not set — no AI work is possible")
        return
    status, data, err = http_json(
        "GET", "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}"})
    if status == 200 and data is not None:
        n = len(data.get("data") or [])
        report("OpenAI (team brain)", "OK",
               f"authenticated; {n} models visible")
    else:
        report("OpenAI (team brain)", "FAILED",
               err or f"unexpected status {status}")


def check_gemini():
    key = env("GEMINI_API_KEY")
    if not key:
        report("Gemini (Imagen images)", "NOT_SET",
               "GEMINI_API_KEY not set — image generation disabled")
        return
    status, data, err = http_json(
        "GET", "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": key})
    if status == 200 and data is not None:
        n = len(data.get("models") or [])
        report("Gemini (Imagen images)", "OK",
               f"authenticated; {n} models visible")
    else:
        report("Gemini (Imagen images)", "FAILED",
               err or f"unexpected status {status}")


def check_telegram():
    token = env("TELEGRAM_BOT_TOKEN")
    chat = env("TELEGRAM_CHAT_ID")
    if not token:
        report("Telegram (publishing)", "NOT_SET",
               "TELEGRAM_BOT_TOKEN not set — Telegram sends skipped")
        return
    status, data, err = http_json(
        "GET", f"https://api.telegram.org/bot{token}/getMe")
    if status == 200 and data and data.get("ok"):
        username = (data.get("result") or {}).get("username", "?")
        chat_note = ("TELEGRAM_CHAT_ID set" if chat
                     else "TELEGRAM_CHAT_ID not set")
        report("Telegram (publishing)", "OK",
               f"bot @{username} authenticated; {chat_note}")
    else:
        detail = err or f"unexpected status {status}"
        if data and data.get("description"):
            detail = f"{detail} ({data['description']})"
        report("Telegram (publishing)", "FAILED", detail)


def check_youtube():
    secrets = env("YOUTUBE_CLIENT_SECRETS")
    if not secrets:
        report("YouTube (uploads)", "NOT_SET",
               "YOUTUBE_CLIENT_SECRETS not set — OAuth client not "
               "created yet (needs Cyrus's Google Cloud step)")
        return
    if not os.path.isfile(secrets):
        report("YouTube (uploads)", "FAILED",
               "configured client-secrets file does not exist: "
               + os.path.basename(secrets))
        return
    token_file = env("YOUTUBE_TOKEN_FILE") or os.path.join(
        os.path.dirname(os.path.abspath(secrets)), "youtube_token.json")
    if not os.path.isfile(token_file):
        report("YouTube (uploads)", "NOT_SET",
               "client secrets present, OAuth token missing — one "
               "Google sign-in by Cyrus still needed")
        return
    # Both files exist: prove the token still refreshes and the
    # channel answers. Any failure here is a configured-key failure.
    try:
        with open(secrets, "r", encoding="utf-8") as f:
            client = json.load(f)
        client = client.get("installed") or client.get("web") or {}
        with open(token_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        refresh = saved.get("refresh_token")
        if not refresh or not client.get("client_id"):
            report("YouTube (uploads)", "FAILED",
                   "token/secrets files present but incomplete "
                   "(no refresh_token or client_id)")
            return
        status, data, err = http_json(
            "POST", "https://oauth2.googleapis.com/token", form={
                "client_id": client["client_id"],
                "client_secret": client.get("client_secret", ""),
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            })
        if status != 200 or not data or not data.get("access_token"):
            report("YouTube (uploads)", "FAILED",
                   f"token refresh failed ({err or status})")
            return
        status, data, err = http_json(
            "GET",
            "https://www.googleapis.com/youtube/v3/channels"
            "?part=id&mine=true",
            headers={"Authorization":
                     f"Bearer {data['access_token']}"})
        if status == 200 and data is not None:
            report("YouTube (uploads)", "OK",
                   "OAuth token refreshes; channel reachable")
        else:
            report("YouTube (uploads)", "FAILED",
                   f"channel check failed ({err or status})")
    except Exception as exc:
        report("YouTube (uploads)", "FAILED",
               f"{type(exc).__name__}: {exc}")


def check_instagram():
    token = env("IG_ACCESS_TOKEN")
    user_id = env("IG_USER_ID")
    missing = [n for n, v in (("IG_ACCESS_TOKEN", token),
                              ("IG_USER_ID", user_id)) if not v]
    if missing:
        report("Instagram (publishing)", "NOT_SET",
               "not set: " + ", ".join(missing) +
               " — Meta token step still pending")
        return
    status, data, err = http_json(
        "GET",
        f"https://graph.facebook.com/v21.0/{user_id}"
        "?fields=id,username",
        headers={"Authorization": f"Bearer {token}"})
    if status == 200 and data is not None:
        report("Instagram (publishing)", "OK",
               f"authenticated as @{data.get('username', '?')}")
    else:
        report("Instagram (publishing)", "FAILED",
               err or f"unexpected status {status}")


def info_lines():
    auto = env("AUTO_PUBLISH")
    gate = ("OPEN — drafts publish without manual approval"
            if auto == "True" else
            "CLOSED — drafts held for manual approval (safe default)")
    report("Approval gate (AUTO_PUBLISH)", "INFO",
           f"AUTO_PUBLISH={auto or '(unset)'} — gate {gate}",
           counts=False)
    ffmpeg = shutil.which("ffmpeg")
    report("Local tool: ffmpeg (renderer)", "OK" if ffmpeg else "NOT_SET",
           "found on PATH" if ffmpeg else "not on PATH — renders "
           "will fail loudly", counts=False)
    report("Local tool: Piper (voice)", *_piper_state(), counts=False)


def _piper_state():
    """Ask the Director's own resolver where Piper lives, so this
    line can never disagree with the agent. Returns (status,
    detail)."""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from smart_agents.director_agent import find_piper

        binary, model = find_piper()
        if binary and model:
            return "OK", "binary + voice model found (Director search)"
        if binary:
            return ("NOT_SET", "piper binary found but no voice "
                    "model — voice will fail loudly")
        return ("NOT_SET", "no piper binary in PIPER_BIN, PATH, or "
                "the house install locations — voice will fail loudly")
    except Exception:
        found = env("PIPER_BIN") or shutil.which("piper")
        if found:
            return "OK", "configured"
        return ("NOT_SET", "PIPER_BIN unset and piper not on PATH")


def main():
    print("Cyrus Team — system health check")
    print("-" * 60)
    check_openai()
    check_gemini()
    check_telegram()
    check_youtube()
    check_instagram()
    info_lines()
    print("-" * 60)
    if _failures:
        print(f"RESULT: NOT READY — configured service(s) FAILED: "
              + ", ".join(_failures))
        return 1
    print("RESULT: READY — every configured service answered OK "
          "(NOT_SET items are warnings, listed above)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
