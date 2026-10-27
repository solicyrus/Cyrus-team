"""CYRUS TEAM — smart_agents/common.py

Shared foundation for the four smart agents: logging setup and
the ONE AI wrapper.

THE AI WRAPPER (adapted from ultimate-robot-team `brain/llm.py`,
the proven honest wrapper, with the game wing's retry pattern from
cyrus-agents game-team/game-architect):

1. PER-ROLE MODEL TIERS. The old team ran EVERYTHING — strategy,
   scripts and judging — on gpt-4o-mini (audit diagnosis #1).
   Now:
     - role "thinking" -> gpt-4o      (Mastermind strategy,
                                       Director scripts, QA judging)
     - role "volume"   -> gpt-4o-mini (captions, prompts, cheap
                                       high-volume work)
2. RETRY WITH BACKOFF: up to 3 attempts, 2s then 5s, retrying only
   transient failures (rate limit / connection / timeout /
   HTTP 429 / 5xx). Non-transient errors fail at once.

House rules:
- The API key comes ONLY from OPENAI_API_KEY. Never stored,
  printed or logged.
- ask()      -> (text, True) on success, (None, False) on failure.
- ask_json() -> (dict, True) on success, (None, False) on failure.
- NEVER raises. No key / no library / no network => (None, False),
  so callers report an honest «نمی‌شه» instead of faking output.
"""

import json
import logging
import os
import time

# Load the repo-root .env (if present) so every agent sees the
# same configuration. Real values live ONLY in that local file —
# never in the repo. Guarded: python-dotenv is a declared
# dependency, but the team must still import cleanly without it.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env"))
except Exception:
    pass

# ------------------------------------------------------------------
# Logging — one setup for the whole team (charter: professional
# logging throughout; no agent prints ad-hoc).
# ------------------------------------------------------------------

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configured = False


def get_logger(name):
    """Return a team logger, configuring the root handler once."""
    global _configured
    if not _configured:
        logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
        _configured = True
    return logging.getLogger(f"cyrus_team.{name}")


log = get_logger("common")

# ------------------------------------------------------------------
# AI wrapper
# ------------------------------------------------------------------

MODEL_TIERS = {
    "thinking": "gpt-4o",
    "volume": "gpt-4o-mini",
}

# Backoff between attempts (seconds): attempt 1 fails -> wait 2s,
# attempt 2 fails -> wait 5s, attempt 3 fails -> give up.
RETRY_DELAYS = (2, 5)


def model_for(role="volume"):
    """Resolve a role name ("thinking"/"volume") to a model id.
    An explicit model id passes through unchanged."""
    if role in MODEL_TIERS:
        return MODEL_TIERS[role]
    return role or MODEL_TIERS["volume"]


def _client():
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        log.warning("openai library not installed — AI unavailable")
        return None
    try:
        return OpenAI(api_key=key, timeout=30)
    except Exception as exc:  # client construction failed
        log.warning("could not create OpenAI client: %s", exc)
        return None


def create_with_retry(client, **kwargs):
    """client.chat.completions.create with retry + backoff.

    Retries only transient errors (rate limit, connection, timeout,
    HTTP 429/5xx). Adapted from the game wing's proven helper.
    """
    from openai import (APIConnectionError, APIError, APITimeoutError,
                        RateLimitError)

    last_exc = None
    for attempt in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except (RateLimitError, APIConnectionError, APITimeoutError) as e:
            last_exc = e
            log.warning("OpenAI transient error (attempt %d/3): %s",
                        attempt + 1, e)
        except APIError as e:
            status = getattr(e, "status_code", None)
            if status is not None and (status == 429 or status >= 500):
                last_exc = e
                log.warning("OpenAI HTTP %s (attempt %d/3)",
                            status, attempt + 1)
            else:
                raise
        if attempt < 2:
            time.sleep(RETRY_DELAYS[attempt])
    raise last_exc


# Team standard (from URT brain/llm.py, 2026-10-23 standing order):
# reason step by step silently, then give only the final answer.
SUPER_THINK = (
    "THINK LIKE A SUPER ROBOT: before answering, silently reason step by step — "
    "(1) what is really being asked? (2) what context do I have? "
    "(3) what is the most helpful, specific answer? "
    "Then give ONLY the final answer, never show your reasoning.\n\n"
)


def ask(prompt, system, role="volume", max_tokens=600, temperature=0.7):
    """Ask the AI for free-form text.

    Returns (text, True) on success, (None, False) on any failure.
    Never raises.
    """
    client = _client()
    if client is None:
        return None, False
    try:
        resp = create_with_retry(
            client,
            model=model_for(role),
            messages=[
                {"role": "system", "content": SUPER_THINK + system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return None, False
        return text, True
    except Exception as exc:
        log.warning("AI ask failed: %s: %s", type(exc).__name__, exc)
        return None, False


def ask_json(prompt, system, role="volume", max_tokens=800,
             temperature=0.5):
    """Ask the AI for a JSON object.

    Returns (dict, True) on success, (None, False) on any failure.
    Never raises.
    """
    text, ok = ask(prompt, system, role=role, max_tokens=max_tokens,
                   temperature=temperature)
    if not ok or not text:
        return None, False
    try:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None, False
        data = json.loads(text[start:end + 1])
        if not isinstance(data, dict):
            return None, False
        return data, True
    except Exception:
        return None, False
